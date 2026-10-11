"""Recruiting, onboarding and engagement: public page, enquiries, events and reservations,
invites, the anonymous member survey and weekly KPI counts.

Privacy rules enforced here:
  * The public page stays hidden until a director publishes it (wording approval first).
  * Enquiries need consent; under-18s need a parent or guardian's name, contact and consent.
  * Enquiries are deleted 6 months after their last status change, or when the person's invite is used.
  * Reservations are deleted 30 days after their event; only the total is kept.
  * Weekly counts never contain names.
  * Survey answers carry no user id; results show only once at least 5 people have answered.
  * Nothing here sends emails or messages.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone

from . import auth, config, db
import random
import sqlite3

from .workflow import WorkflowError, now_iso, require_role

STAFF_COMMUNITY = ("director", "welcome")
KPI_ROLES = ("director", "welcome", "comms")
INTERESTS = ("sing", "volunteer", "support", "concert")
VOICE_TYPES = ("not sure", "soprano", "alto", "tenor", "bass")
STATUSES = ("new", "contacted", "first_rehearsal", "probation", "joined", "volunteer", "not_now")
SOURCES = ("whatsapp", "instagram", "facebook", "youtube", "qr", "poster", "mass", "friend", "web", "email")
ENQUIRY_RETENTION_DAYS = 183
RESERVATION_RETENTION_DAYS = 30
INVITE_DAYS = 14
SURVEY_MIN_RESPONSES = 5
MAX_PARTY = 10

SETTINGS_DEFAULTS = {
    "published": "0",
    "choir_name": "the English Choir of St. Stephen's Basilica",
    "headline": "Come sing with us",
    "mission": "Sing praises to God, in St. Stephen's and all over the world.",
    "about": "We sing at the English Mass in St. Stephen's Basilica, Budapest. Singers of every nationality "
             "and background are welcome. You don't need to read music perfectly; you need to love singing.",
    "rehearsals": "[Rehearsal day, time and place to be confirmed]",
    "what_to_expect": "Come to one rehearsal and listen or sing along. New singers sing with us for four weeks "
                      "before joining the choir in concerts.",
    "join_deadline": "",  # YYYY-MM-DD; shown as "to sing at the Christmas Concert, please start by ..."
    "join_deadline_text": "To sing at the Christmas Concert, please sign up by",
    "support_text": "Can't sing with us? You can still help: volunteer at a concert, share our posts, "
                    "or come and listen.",
    "donation_url": "",  # only a parish or charity page; the choir itself handles no money
    "donation_text": "",
    "privacy_text": "Only the choir's welcome team sees what you send. We use it only to reply to you, and we "
                    "delete it after 6 months. We never send automatic messages.",
}
SETTING_LIMITS = {k: 2000 for k in SETTINGS_DEFAULTS} | {"donation_url": 300, "join_deadline": 10, "published": 1}

_rate: dict[str, list[float]] = {}


def today() -> str:
    return date.today().isoformat()


def iso_week(d: date | None = None) -> str:
    iso = (d or date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def rate_limited(key: str, limit: int = 5, window: float = 600.0) -> bool:
    """True if `key` already has `limit` successful submissions in the window. In memory only:
    client addresses are never written to disk."""
    now = time.time()
    _rate[key] = [t for t in _rate.get(key, []) if now - t < window]
    return len(_rate[key]) >= limit


def rate_record(key: str) -> None:
    _rate.setdefault(key, []).append(time.time())


def _clean(text, limit: int, required: bool = False, what: str = "This field") -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text or "")).strip()
    if required and not text:
        raise WorkflowError(f"{what} is required")
    if len(text) > limit:
        raise WorkflowError(f"{what} is too long (maximum {limit} characters)")
    return text


def _source(value) -> str | None:
    value = (value or "").strip().lower()
    return value if value in SOURCES else None


# ---- Public page settings ---------------------------------------------------------------

def get_settings() -> dict:
    out = dict(SETTINGS_DEFAULTS)
    with db.closing() as conn:
        for row in conn.execute("SELECT key, value FROM site_settings"):
            if row["key"] in out:
                out[row["key"]] = row["value"]
    return out


def update_settings(user, values: dict) -> dict:
    require_role(user, "director")
    clean = {}
    for key, value in values.items():
        if key not in SETTINGS_DEFAULTS:
            raise WorkflowError(f"Unknown setting: {key}")
        clean[key] = _clean(value, SETTING_LIMITS[key], what=key)
    if clean.get("join_deadline"):
        try:
            date.fromisoformat(clean["join_deadline"])
        except ValueError as exc:
            raise WorkflowError("Sign-up deadline must be a date like 2026-10-24") from exc
    if "published" in clean and clean["published"] not in ("0", "1"):
        raise WorkflowError("published must be 0 or 1")
    if clean.get("donation_url") and not clean["donation_url"].startswith("https://"):
        raise WorkflowError("The donation link must start with https://")
    with db.transaction() as conn:
        for key, value in clean.items():
            conn.execute("INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET "
                         "value = excluded.value", (key, value))
    return get_settings()


def public_page(viewer=None) -> dict:
    s = get_settings()
    staff = viewer is not None and viewer["role"] in ("director", "welcome", "comms")
    if s["published"] != "1" and not staff:
        raise LookupError("This page is not published yet")
    return {"settings": {k: v for k, v in s.items()}, "events": public_events(), "preview": s["published"] != "1"}


# ---- Events ----------------------------------------------------------------------------

def _parse_start(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowError("Start must be a date and time like 2026-12-13T19:00") from exc
    if dt.tzinfo is None:
        from zoneinfo import ZoneInfo
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Budapest"))
    return dt.isoformat(timespec="minutes")


def save_event(user, data: dict, event_id: int | None = None) -> int:
    require_role(user, "director")
    fields = {
        "title": _clean(data.get("title"), 120, True, "Title"),
        "starts_at": _parse_start(data.get("starts_at")),
        "venue": _clean(data.get("venue"), 200, what="Venue"),
        "description": _clean(data.get("description"), 2000, what="Description"),
        "is_public": 1 if data.get("is_public") else 0,
        "rsvp_open": 1 if data.get("rsvp_open") else 0,
        "capacity": int(data["capacity"]) if data.get("capacity") not in (None, "") else None,
        "actual_attendance": int(data["actual_attendance"]) if data.get("actual_attendance") not in (None, "") else None,
        "donations_reported_huf": int(data["donations_reported_huf"])
        if data.get("donations_reported_huf") not in (None, "") else None,
    }
    for key in ("capacity", "actual_attendance", "donations_reported_huf"):
        if fields[key] is not None and fields[key] < 0:
            raise WorkflowError("Numbers cannot be negative")
    with db.transaction() as conn:
        if event_id is None:
            cur = conn.execute(
                "INSERT INTO events (title, starts_at, venue, description, is_public, rsvp_open, capacity, "
                "actual_attendance, donations_reported_huf, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*fields.values(), now_iso()))
            return cur.lastrowid
        if conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None:
            raise LookupError("Event not found")
        conn.execute("UPDATE events SET " + ", ".join(f"{k} = ?" for k in fields) + " WHERE id = ?",
                     (*fields.values(), event_id))
        return event_id


def _reserved(conn, event_id: int) -> int:
    return conn.execute("SELECT COALESCE(SUM(party_size), 0) FROM reservations WHERE event_id = ? AND cancelled = 0",
                        (event_id,)).fetchone()[0]


def public_events() -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    with db.closing() as conn:
        for e in conn.execute("SELECT * FROM events WHERE is_public = 1 ORDER BY starts_at"):
            if datetime.fromisoformat(e["starts_at"]) < now - timedelta(hours=6):
                continue
            reserved = _reserved(conn, e["id"])
            out.append({"id": e["id"], "title": e["title"], "starts_at": e["starts_at"], "venue": e["venue"],
                        "description": e["description"], "rsvp_open": bool(e["rsvp_open"]),
                        "places_left": None if e["capacity"] is None else max(0, e["capacity"] - reserved)})
    return out


def list_events(user) -> list[dict]:
    require_role(user, *KPI_ROLES)
    with db.closing() as conn:
        rows = []
        for e in conn.execute("SELECT * FROM events ORDER BY starts_at DESC"):
            item = dict(e)
            item["reserved"] = _reserved(conn, e["id"]) if e["reservations_final"] is None else e["reservations_final"]
            rows.append(item)
        return rows


# ---- Enquiries (interest form) -------------------------------------------------------------

def submit_enquiry(data: dict) -> None:
    if data.get("website"):  # honeypot: humans never see this field
        return
    if not data.get("consent"):
        raise WorkflowError("Please tick the box to agree to how we use your details")
    interests = [i for i in (data.get("interests") or []) if i in INTERESTS]
    if not interests:
        raise WorkflowError("Please choose at least one thing you'd like to do")
    voice = (data.get("voice_type") or "not sure").lower() if "sing" in interests else None
    if voice is not None and voice not in VOICE_TYPES:
        raise WorkflowError("Unknown voice type")
    under_18 = bool(data.get("under_18"))
    guardian_name = guardian_contact = None
    if under_18:
        guardian_name = _clean(data.get("guardian_name"), 80, True, "Parent or guardian's name")
        guardian_contact = _clean(data.get("guardian_contact"), 120, True, "Parent or guardian's contact")
        if not data.get("guardian_consent"):
            raise WorkflowError("A parent or guardian must agree before we can contact someone under 18")
    rec = {
        "id": secrets.token_hex(12), "created_on": today(),
        "first_name": _clean(data.get("first_name"), 60, True, "First name"),
        "contact": _clean(data.get("contact"), 120, True, "Email or phone"),
        "interests": json.dumps(interests), "voice_type": voice,
        "message": _clean(data.get("message"), 1000, what="Message"),
        "under_18": int(under_18), "guardian_name": guardian_name, "guardian_contact": guardian_contact,
        "updates_opt_in": 1 if data.get("updates_opt_in") else 0, "source": _source(data.get("source")),
        "status": "new", "status_changed_on": today(),
    }
    with db.transaction() as conn:
        conn.execute("INSERT INTO enquiries (" + ", ".join(rec) + ") VALUES (" + ", ".join("?" * len(rec)) + ")",
                     tuple(rec.values()))
        conn.execute("INSERT INTO enquiry_events (ref, status, on_date, interests) VALUES (?, 'new', ?, ?)",
                     (rec["id"], today(), rec["interests"]))


def list_enquiries(user) -> list[dict]:
    require_role(user, *STAFF_COMMUNITY)
    purge_expired()
    with db.closing() as conn:
        rows = conn.execute("SELECT * FROM enquiries ORDER BY created_on DESC, rowid DESC").fetchall()
    return [{**dict(r), "interests": json.loads(r["interests"])} for r in rows]


def update_enquiry(user, enquiry_id: str, status: str | None = None, notes: str | None = None) -> None:
    require_role(user, *STAFF_COMMUNITY)
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
        if row is None:
            raise LookupError("Enquiry not found")
        if status is not None and status != row["status"]:
            if status not in STATUSES:
                raise WorkflowError("Unknown status")
            conn.execute("UPDATE enquiries SET status = ?, status_changed_on = ? WHERE id = ?",
                         (status, today(), enquiry_id))
            conn.execute("INSERT INTO enquiry_events (ref, status, on_date, interests) VALUES (?, ?, ?, ?)",
                         (enquiry_id, status, today(), row["interests"]))
        if notes is not None:
            conn.execute("UPDATE enquiries SET notes = ? WHERE id = ?", (_clean(notes, 2000, what="Notes"), enquiry_id))


def delete_enquiry(user, enquiry_id: str) -> None:
    require_role(user, *STAFF_COMMUNITY)
    with db.transaction() as conn:
        if conn.execute("DELETE FROM enquiries WHERE id = ?", (enquiry_id,)).rowcount == 0:
            raise LookupError("Enquiry not found")


# ---- Reservations ------------------------------------------------------------------------

def reserve(data: dict) -> dict:
    if data.get("website"):
        return {"cancel_code": None}
    if not data.get("consent"):
        raise WorkflowError("Please tick the box to agree to how we use your details")
    try:
        party = int(data.get("party_size") or 1)
    except (TypeError, ValueError) as exc:
        raise WorkflowError("Number of people must be a number") from exc
    if not 1 <= party <= MAX_PARTY:
        raise WorkflowError(f"You can reserve for 1 to {MAX_PARTY} people")
    first_name = _clean(data.get("first_name"), 60, True, "First name")
    contact = _clean(data.get("contact"), 120, True, "Email or phone")
    code = secrets.token_urlsafe(9)
    with db.transaction() as conn:
        e = conn.execute("SELECT * FROM events WHERE id = ? AND is_public = 1", (data.get("event_id"),)).fetchone()
        if e is None or not e["rsvp_open"]:
            raise LookupError("Reservations are not open for this event")
        if datetime.fromisoformat(e["starts_at"]) < datetime.now(timezone.utc):
            raise WorkflowError("This event has already started")
        if e["capacity"] is not None and _reserved(conn, e["id"]) + party > e["capacity"]:
            raise WorkflowError("Sorry, there are not enough places left")
        conn.execute("INSERT INTO reservations (id, event_id, first_name, contact, party_size, updates_opt_in, source, "
                     "cancel_hash, created_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (secrets.token_hex(12), e["id"], first_name, contact, party,
                      1 if data.get("updates_opt_in") else 0, _source(data.get("source")), _hash(code), today()))
    return {"cancel_code": code}


def cancel_reservation(code: str) -> None:
    with db.transaction() as conn:
        if conn.execute("UPDATE reservations SET cancelled = 1 WHERE cancel_hash = ? AND cancelled = 0",
                        (_hash(code or ""),)).rowcount == 0:
            raise LookupError("No active reservation found for that code")


def list_reservations(user, event_id: int) -> list[dict]:
    require_role(user, *STAFF_COMMUNITY)
    with db.closing() as conn:
        rows = conn.execute("SELECT first_name, contact, party_size, source, created_on, cancelled FROM reservations "
                            "WHERE event_id = ? ORDER BY created_on", (event_id,)).fetchall()
    return [dict(r) for r in rows]


# ---- Retention ---------------------------------------------------------------------------

def purge_expired() -> dict:
    cutoff = (date.today() - timedelta(days=ENQUIRY_RETENTION_DAYS)).isoformat()
    removed = {}
    with db.transaction() as conn:
        removed["enquiries"] = conn.execute("DELETE FROM enquiries WHERE status_changed_on < ?", (cutoff,)).rowcount
        removed["reservations"] = 0
        old_cut = datetime.now(timezone.utc) - timedelta(days=RESERVATION_RETENTION_DAYS)
        for e in conn.execute("SELECT id, starts_at, reservations_final FROM events").fetchall():
            if datetime.fromisoformat(e["starts_at"]) < old_cut:
                if e["reservations_final"] is None:
                    conn.execute("UPDATE events SET reservations_final = ? WHERE id = ?",
                                 (_reserved(conn, e["id"]), e["id"]))
                removed["reservations"] += conn.execute("DELETE FROM reservations WHERE event_id = ?",
                                                        (e["id"],)).rowcount
    return removed


# ---- Invites (easy sign-in) ------------------------------------------------------------------

def create_invite(user, display_name: str, role: str, voice_part: str | None = None,
                  enquiry_id: str | None = None) -> dict:
    require_role(user, "director")
    if role not in ("singer", "voice_lead", "director", "welcome", "comms"):
        raise WorkflowError("Unknown role")
    if voice_part not in (None, "", "S", "A", "T", "B"):
        raise WorkflowError("Voice part must be S, A, T or B")
    voice_part = voice_part or None
    if role == "voice_lead" and not voice_part:
        raise WorkflowError("A voice lead needs a voice part")
    display_name = _clean(display_name, 60, True, "Name")
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS)).replace(microsecond=0).isoformat()
    with db.transaction() as conn:
        if enquiry_id and conn.execute("SELECT 1 FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone() is None:
            raise LookupError("Enquiry not found")
        cur = conn.execute("INSERT INTO invites (token_hash, display_name, role, voice_part, enquiry_id, created_by, "
                           "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (_hash(token), display_name, role, voice_part, enquiry_id, user["id"], now_iso(), expires))
    return {"id": cur.lastrowid, "token": token, "expires_at": expires}


def resend_invite(user, invite_id: int) -> dict:
    """Issue a fresh link for the same person; the old link stops working."""
    require_role(user, "director")
    with db.transaction() as conn:
        inv = conn.execute("SELECT * FROM invites WHERE id = ?", (invite_id,)).fetchone()
        if inv is None:
            raise LookupError("Invite not found")
        if inv["used_at"]:
            raise WorkflowError("This invite has already been used")
        conn.execute("UPDATE invites SET revoked = 1 WHERE id = ?", (invite_id,))
    return create_invite(user, inv["display_name"], inv["role"], inv["voice_part"], inv["enquiry_id"])


def list_invites(user) -> list[dict]:
    require_role(user, "director")
    now = datetime.now(timezone.utc).isoformat()
    with db.closing() as conn:
        rows = conn.execute("SELECT id, display_name, role, voice_part, created_at, expires_at, used_at, revoked "
                            "FROM invites ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        state = "used" if r["used_at"] else "replaced" if r["revoked"] else "expired" if r["expires_at"] < now \
            else "pending"
        out.append({**dict(r), "state": state})
    return out


def _live_invite(conn, token: str):
    inv = conn.execute("SELECT * FROM invites WHERE token_hash = ?", (_hash(token or ""),)).fetchone()
    if inv is None or inv["used_at"] or inv["revoked"] or inv["expires_at"] < datetime.now(timezone.utc).isoformat():
        raise LookupError("This invite link is not valid any more. Ask the choir for a new one.")
    return inv


def check_invite(token: str) -> dict:
    with db.closing() as conn:
        inv = _live_invite(conn, token)
    return {"display_name": inv["display_name"], "role": inv["role"], "voice_part": inv["voice_part"]}


USERNAME_RX = re.compile(r"^[a-z0-9_.-]{3,32}$")


def accept_invite(token: str, username: str, password: str) -> str:
    """Create the account from the invite (role and part come from the invite) and return a session token."""
    username = (username or "").strip().lower()
    if not USERNAME_RX.match(username):
        raise WorkflowError("Username: 3–32 lowercase letters, numbers, dots, dashes or underscores")
    if len(password or "") < 10:
        raise WorkflowError("Password must be at least 10 characters")
    with db.transaction() as conn:
        inv = _live_invite(conn, token)
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise WorkflowError("That username is taken; please choose another")
        conn.execute("INSERT INTO users (username, display_name, password_hash, role, voice_part) VALUES (?, ?, ?, ?, ?)",
                     (username, inv["display_name"], auth.hash_password(password), inv["role"], inv["voice_part"]))
        conn.execute("UPDATE invites SET used_at = ? WHERE id = ?", (now_iso(), inv["id"]))
        if inv["enquiry_id"]:
            # Their details now live in the member account; the enquiry record is no longer needed.
            row = conn.execute("SELECT interests FROM enquiries WHERE id = ?", (inv["enquiry_id"],)).fetchone()
            if row is not None:
                conn.execute("INSERT INTO enquiry_events (ref, status, on_date, interests) VALUES (?, 'joined', ?, ?)",
                             (inv["enquiry_id"], today(), row["interests"]))
                conn.execute("DELETE FROM enquiries WHERE id = ?", (inv["enquiry_id"],))
    session = auth.login(username, password)
    if session is None:
        raise WorkflowError("Account created; please log in")
    return session


# ---- Member survey (NPS) ---------------------------------------------------------------------

MEMBER_ROLES = ("singer", "voice_lead", "director", "welcome", "comms")


def create_survey(user, title: str, question: str | None = None) -> int:
    require_role(user, "director")
    q = question or "How likely are you to recommend singing with our choir to a friend? (0 = not at all, 10 = very)"
    with db.transaction() as conn:
        cur = conn.execute("INSERT INTO surveys (title, question, created_at) VALUES (?, ?, ?)",
                           (_clean(title, 80, True, "Title"), _clean(q, 300, True, "Question"), now_iso()))
        return cur.lastrowid


def close_survey(user, survey_id: int) -> None:
    require_role(user, "director")
    with db.transaction() as conn:
        if conn.execute("UPDATE surveys SET is_open = 0 WHERE id = ?", (survey_id,)).rowcount == 0:
            raise LookupError("Survey not found")


def _voter_hash(survey_id: int, user_id: int) -> str:
    # Keyed so the table cannot be matched to users by recomputing simple hashes.
    secret = (config.DATA_DIR / ".survey-key")
    if not secret.exists():
        secret.write_text(secrets.token_hex(32))
    return hashlib.sha256(f"{secret.read_text()}:{survey_id}:{user_id}".encode()).hexdigest()


def open_surveys(user) -> list[dict]:
    require_role(user, *MEMBER_ROLES)
    with db.closing() as conn:
        rows = conn.execute("SELECT id, title, question FROM surveys WHERE is_open = 1 ORDER BY id").fetchall()
        out = []
        for r in rows:
            voted = conn.execute("SELECT 1 FROM survey_voters WHERE survey_id = ? AND voter_hash = ?",
                                 (r["id"], _voter_hash(r["id"], user["id"]))).fetchone() is not None
            out.append({**dict(r), "answered": voted})
    return out


def answer_survey(user, survey_id: int, score: int, comment: str = "") -> None:
    require_role(user, *MEMBER_ROLES)
    if not isinstance(score, int) or not 0 <= score <= 10:
        raise WorkflowError("Choose a number from 0 to 10")
    comment = _clean(comment, 1000, what="Comment")
    with db.transaction() as conn:
        s = conn.execute("SELECT is_open FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if s is None or not s["is_open"]:
            raise LookupError("This survey is closed")
        try:
            conn.execute("INSERT INTO survey_voters (survey_id, voter_hash) VALUES (?, ?)",
                         (survey_id, _voter_hash(survey_id, user["id"])))
        except sqlite3.IntegrityError as exc:  # primary key clash = already answered
            raise WorkflowError("You have already answered this survey. Thank you!") from exc
        conn.execute("INSERT INTO survey_answers (id, survey_id, score, comment) VALUES (?, ?, ?, ?)",
                     (secrets.token_hex(12), survey_id, score, comment))


def survey_results(user) -> list[dict]:
    require_role(user, "director")
    out = []
    with db.closing() as conn:
        for s in conn.execute("SELECT * FROM surveys ORDER BY id DESC").fetchall():
            answers = conn.execute("SELECT score, comment FROM survey_answers WHERE survey_id = ?",
                                   (s["id"],)).fetchall()
            n = len(answers)
            item = {"id": s["id"], "title": s["title"], "question": s["question"], "is_open": bool(s["is_open"]),
                    "responses": n}
            if n >= SURVEY_MIN_RESPONSES:
                promoters = sum(1 for a in answers if a["score"] >= 9)
                detractors = sum(1 for a in answers if a["score"] <= 6)
                item.update(nps=round(100 * (promoters - detractors) / n), promoters=promoters,
                            passives=n - promoters - detractors, detractors=detractors,
                            comments=random.sample(comments := [a["comment"] for a in answers if a["comment"]],
                                                   len(comments)))
            else:
                item["note"] = f"Results appear once at least {SURVEY_MIN_RESPONSES} people have answered."
            out.append(item)
    return out


# ---- KPIs --------------------------------------------------------------------------------------

def weekly_counts(weeks: int = 12) -> list[dict]:
    """Counts per ISO week from the anonymous status history. No names."""
    start = date.today() - timedelta(weeks=weeks - 1, days=date.today().weekday())
    buckets: dict[str, dict] = {}
    for i in range(weeks):
        wk = iso_week(start + timedelta(weeks=i))
        buckets[wk] = {"week": wk, "enquiries": 0, "singers": 0, "volunteers_supporters": 0, "contacted": 0,
                       "first_rehearsal": 0, "probation": 0, "joined": 0}
    with db.closing() as conn:
        for ev in conn.execute("SELECT status, on_date, interests FROM enquiry_events WHERE on_date >= ?",
                               (start.isoformat(),)):
            wk = iso_week(date.fromisoformat(ev["on_date"]))
            b = buckets.get(wk)
            if b is None:
                continue
            interests = json.loads(ev["interests"] or "[]")
            if ev["status"] == "new":
                b["enquiries"] += 1
                if "sing" in interests:
                    b["singers"] += 1
                if {"volunteer", "support"} & set(interests):
                    b["volunteers_supporters"] += 1
            elif ev["status"] in b:
                b[ev["status"]] += 1
    return list(buckets.values())


def kpi_summary(user) -> dict:
    require_role(user, *KPI_ROLES)
    purge_expired()
    with db.closing() as conn:
        snapshots = [dict(r) for r in conn.execute(
            "SELECT week, metric, value FROM kpi_snapshots ORDER BY week DESC, metric LIMIT 200")]
        sources = [dict(r) for r in conn.execute(
            "SELECT COALESCE(source, 'unknown') AS source, COUNT(*) AS n FROM enquiries GROUP BY 1 ORDER BY 2 DESC")]
        totals = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(DISTINCT ref) AS n FROM enquiry_events GROUP BY status")}
    return {"weeks": weekly_counts(), "totals": totals, "sources_open_enquiries": sources,
            "snapshots": snapshots, "events": list_events(user)}


def kpi_csv(user) -> str:
    require_role(user, *KPI_ROLES)
    buf = io.StringIO()
    rows = weekly_counts()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


KPI_METRICS = ("followers_instagram", "followers_facebook", "followers_youtube", "followers_tiktok",
               "active_singers", "volunteers", "rehearsal_attendance")


def save_snapshot(user, metric: str, value: int, week: str | None = None) -> None:
    require_role(user, "director", "comms")
    if metric not in KPI_METRICS:
        raise WorkflowError("Unknown measure")
    if not isinstance(value, int) or value < 0:
        raise WorkflowError("Value must be a whole number, 0 or more")
    week = week or iso_week()
    if not re.fullmatch(r"\d{4}-W\d{2}", week):
        raise WorkflowError("Week must look like 2026-W42")
    with db.transaction() as conn:
        conn.execute("INSERT INTO kpi_snapshots (week, metric, value) VALUES (?, ?, ?) ON CONFLICT(week, metric) "
                     "DO UPDATE SET value = excluded.value", (week, metric, value))

