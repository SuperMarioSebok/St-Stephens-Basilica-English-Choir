"""Songs, immutable versions, part-level permissions and the approval gate.

Rules enforced here (not in the UI):
  * Singers see a song only through its single APPROVED version.
  * Voice Leads change only their own part. Directors may change any part.
  * Any content change creates a new draft version, revokes the song's current
    approval and queues audio regeneration.
  * Approval applies to one exact version and only if it is the latest one.
"""
from __future__ import annotations

import copy
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from . import config, db
from . import musicxml_import as mxi
from .model import PART_NAMES, VOICE_PARTS, ModelError, format_bar_tokens, parse_bar_tokens
from .safe_upload import UploadError, check_audio, check_pdf, load_score_upload

CONTENT_FLAG_CODES_PER_BAR = {"divisi", "possible-unison", "overflow", "overlap"}


class WorkflowError(ValueError):
    """Request is understood but not allowed in the current state (HTTP 409/400)."""


class Forbidden(PermissionError):
    """Role or part does not permit this (HTTP 403)."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def song_dir(song_id: int) -> Path:
    d = config.STORAGE_DIR / "songs" / str(int(song_id))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store(song_id: int, sub: str, ext: str, data: bytes) -> str:
    """Write bytes under a server-chosen name; return the path relative to STORAGE_DIR."""
    folder = song_dir(song_id) / sub
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(12)}.{ext}"
    (folder / name).write_bytes(data)
    return str((folder / name).relative_to(config.STORAGE_DIR))


def _read_storage(rel: str) -> bytes:
    path = (config.STORAGE_DIR / rel).resolve()
    if config.STORAGE_DIR.resolve() not in path.parents:
        raise WorkflowError("Invalid storage path")
    return path.read_bytes()


# ---- Permission helpers --------------------------------------------------------

def require_role(user, *roles):
    if user is None or user["role"] not in roles:
        raise Forbidden("Your role cannot do this")


def require_part(user, part: str):
    if part not in VOICE_PARTS:
        raise WorkflowError("Unknown voice part")
    if user["role"] == "director":
        return
    if user["role"] == "voice_lead" and user["voice_part"] == part:
        return
    raise Forbidden("You can only edit your own voice part")


def get_version(conn, vid: int):
    row = conn.execute("SELECT v.*, s.kind AS song_kind, s.title AS song_title FROM versions v "
                       "JOIN songs s ON s.id = v.song_id WHERE v.id = ?", (vid,)).fetchone()
    if row is None:
        raise LookupError("Version not found")
    return row


def latest_version_id(conn, song_id: int) -> int:
    return conn.execute("SELECT MAX(id) FROM versions WHERE song_id = ?", (song_id,)).fetchone()[0]


def approved_version(conn, song_id: int):
    return conn.execute("SELECT * FROM versions WHERE song_id = ? AND status = 'approved'", (song_id,)).fetchone()


def can_view_version(user, version) -> bool:
    if user is None:
        return False
    if user["role"] in ("director", "voice_lead"):
        return True
    return version["status"] == "approved"


def render_state(conn, vid: int) -> dict:
    job = conn.execute("SELECT status, attempts, max_attempts, error FROM jobs WHERE version_id = ? "
                       "ORDER BY id DESC LIMIT 1", (vid,)).fetchone()
    return dict(job) if job else {"status": "none"}


# ---- Creating songs --------------------------------------------------------------

def create_score_song(user, filename: str, data: bytes, rights_note: str, is_test_piece: bool = False,
                      title: str | None = None) -> dict:
    require_role(user, "director")
    if not (rights_note or "").strip():
        raise WorkflowError("Record who owns the arrangement and what permission the choir has")
    xml = load_score_upload(filename, data)
    inv = mxi.inspect(xml)
    mapping = mxi.propose_mapping(inv)
    model = mxi.build_model(inv, mapping)
    with db.transaction() as conn:
        cur = conn.execute("INSERT INTO songs (title, kind, rights_note, is_test_piece, created_by, created_at) "
                           "VALUES (?, 'score', ?, ?, ?, ?)",
                           (title or inv["title"], rights_note.strip(), int(is_test_piece), user["id"], now_iso()))
        song_id = cur.lastrowid
        src = _store(song_id, "sources", "musicxml", xml)
        vid = _insert_version(conn, user, song_id, None, model, mapping, src, "Imported MusicXML",
                              [("import", None, {"file": "uploaded score", "proposed_mapping": _mapping_summary(mapping)})])
    return {"song_id": song_id, "version_id": vid}


def create_manual_song(user, title: str, rights_note: str, audio_name: str, audio: bytes, pdf: bytes | None,
                       bar_hint: str = "") -> dict:
    """Fallback path: an authorized recording plus PDF, with time-based loops only."""
    require_role(user, "director")
    if not (title or "").strip() or not (rights_note or "").strip():
        raise WorkflowError("Title and rights note are required")
    ext = check_audio(audio_name, audio)
    if pdf is not None:
        check_pdf(pdf)
    with db.transaction() as conn:
        cur = conn.execute("INSERT INTO songs (title, kind, rights_note, is_test_piece, created_by, created_at) "
                           "VALUES (?, 'manual', ?, 0, ?, ?)", (title.strip(), rights_note.strip(), user["id"], now_iso()))
        song_id = cur.lastrowid
        vid = _insert_version(conn, user, song_id, None, None, None, None, "Uploaded practice track and PDF",
                              [("manual-upload", None, {"audio": ext, "pdf": pdf is not None})],
                              manual={"note": bar_hint[:500]})
        from .safe_upload import AUDIO_MIME
        _add_asset(conn, vid, "source_audio", None, 100, _store(song_id, f"v{vid}", ext, audio), AUDIO_MIME[ext])
        if pdf is not None:
            _add_asset(conn, vid, "pdf", None, None, _store(song_id, f"v{vid}", "pdf", pdf), "application/pdf")
        conn.execute("INSERT INTO jobs (version_id, kind, status, max_attempts, queued_at, finished_at) "
                     "VALUES (?, 'none', 'done', 0, ?, ?)", (vid, now_iso(), now_iso()))
    return {"song_id": song_id, "version_id": vid}


def _add_asset(conn, vid, kind, part, tempo, rel, mime, seconds=None) -> str:
    aid = secrets.token_urlsafe(18)
    conn.execute("INSERT INTO assets (id, version_id, kind, part, tempo, rel_path, mime, seconds) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (aid, vid, kind, part, tempo, rel, mime, seconds))
    return aid


def _mapping_summary(mapping):
    return {vp: (None if not m or not m.get("part_id") else f"{m['part_id']}/staff {m['staff']}/voice {m['voice']}")
            for vp, m in (mapping or {}).items()}


def _insert_version(conn, user, song_id, parent, model, mapping, source_file, summary, changes, manual=None) -> int:
    number = (conn.execute("SELECT COALESCE(MAX(number), 0) FROM versions WHERE song_id = ?",
                           (song_id,)).fetchone()[0]) + 1
    # Any new version cancels the current approval and any pending review.
    conn.execute("UPDATE versions SET status = 'revoked' WHERE song_id = ? AND status = 'approved'", (song_id,))
    conn.execute("UPDATE versions SET status = 'superseded' WHERE song_id = ? AND status IN ('in_review', 'draft', "
                 "'rejected')", (song_id,))
    cur = conn.execute(
        "INSERT INTO versions (song_id, number, parent_id, status, source_file, mapping_json, model_json, manual_json, "
        "created_by, created_at, change_summary) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)",
        (song_id, number, parent, source_file, json.dumps(mapping) if mapping else None,
         json.dumps(model) if model else None, json.dumps(manual) if manual else None,
         user["id"], now_iso(), summary[:300]))
    vid = cur.lastrowid
    for action, part, detail in changes:
        conn.execute("INSERT INTO changes (version_id, user_id, at, action, part, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
                     (vid, user["id"], now_iso(), action, part, json.dumps(detail)))
    if model is not None:
        conn.execute("INSERT INTO jobs (version_id, kind, status, max_attempts, queued_at) VALUES (?, 'render', "
                     "'queued', ?, ?)", (vid, config.JOB_MAX_ATTEMPTS, now_iso()))
    return vid


def _editable(conn, user, vid: int, part: str):
    require_role(user, "director", "voice_lead")
    require_part(user, part)
    v = get_version(conn, vid)
    if v["song_kind"] != "score":
        raise WorkflowError("Uploaded-recording songs have no editable parts")
    if v["id"] != latest_version_id(conn, v["song_id"]):
        raise WorkflowError("This is not the latest version. Reload and edit the latest one.")
    return v, json.loads(v["model_json"]), json.loads(v["mapping_json"])


# ---- Edits (each creates a new version) ---------------------------------------------

def edit_bars(user, vid: int, part: str, bars: dict, summary: str = "") -> int:
    if not bars:
        raise WorkflowError("No bars changed")
    with db.transaction() as conn:
        v, model, mapping = _editable(conn, user, vid, part)
        p = model["parts"].get(part)
        if p is None:
            raise WorkflowError(f"{PART_NAMES[part]} is not mapped yet; map it first")
        new = copy.deepcopy(model)
        diffs = []
        for key, tokens in bars.items():
            idx = int(key)
            if not 0 <= idx < len(model["bars"]):
                raise WorkflowError(f"Bar index {idx} does not exist")
            try:
                notes = parse_bar_tokens(tokens, model["bars"][idx]["ticks"])
            except ModelError as exc:
                raise WorkflowError(f"Bar {model['bars'][idx]['label']}: {exc}") from exc
            before = format_bar_tokens(p["bars"][idx])
            after = format_bar_tokens(notes)
            if before != after:
                new["parts"][part]["bars"][idx] = notes
                diffs.append({"bar": model["bars"][idx]["label"], "before": before, "after": after})
                new["flags"] = [f for f in new["flags"] if not (f["part"] == part and f["bar"] == idx
                                                                and f["code"] in CONTENT_FLAG_CODES_PER_BAR)]
                if any(len(n["p"]) > 1 for n in notes):
                    new["flags"].append({"level": "warn", "code": "divisi", "part": part, "bar": idx,
                                         "message": f"{PART_NAMES[part]} has a chord (divisi?) in bar "
                                                    f"{model['bars'][idx]['label']}. Confirm who sings what."})
        if not diffs:
            raise WorkflowError("Nothing changed")
        text = summary.strip() or f"{PART_NAMES[part]}: edited bar(s) {', '.join(d['bar'] for d in diffs)}"
        return _insert_version(conn, user, v["song_id"], vid, new, mapping, v["source_file"], text,
                               [("edit-notes", part, {"bars": diffs})])


def _inventory_for(v, entry) -> dict:
    rel = (entry or {}).get("source_file") or v["source_file"]
    return mxi.inspect(_read_storage(rel))


def _replace_part(model, part, bars, flags, clef, label):
    new = copy.deepcopy(model)
    new["parts"][part] = None if bars is None else {"label": label, "clef": clef["name"], "bars": bars}
    new["flags"] = [f for f in new["flags"] if f["part"] != part] + flags
    return new


def set_mapping(user, vid: int, part: str, entry: dict, confirm: bool = True) -> int:
    return set_mappings(user, vid, {part: entry}, confirm)


def set_mappings(user, vid: int, entries: dict, confirm: bool = True) -> int:
    """Set (and usually confirm) the source mapping for one or more parts in ONE new version."""
    if not entries:
        raise WorkflowError("No mapping given")
    with db.transaction() as conn:
        for part in entries:
            require_role(user, "director", "voice_lead")
            require_part(user, part)
        v, model, mapping = _editable(conn, user, vid, next(iter(entries)))
        new_model, new_mapping, changes = model, dict(mapping), []
        for part, entry in entries.items():
            old = mapping.get(part) or {}
            none = bool(entry.get("none"))
            new_entry = {
                "part_id": None if none else entry.get("part_id"),
                "staff": None if none else (int(entry["staff"]) if entry.get("staff") is not None else None),
                "voice": None if none else (str(entry["voice"]) if entry.get("voice") is not None else None),
                "octave_shift": 0 if none else int(entry.get("octave_shift") or 0),
                "confirmed": bool(confirm), "confirmed_by": user["username"] if confirm else None,
                "label": old.get("label") or PART_NAMES[part],
                "source_file": old.get("source_file") if _same_source(old, entry) else None,
            }
            if new_entry["octave_shift"] not in (-2, -1, 0, 1, 2):
                raise WorkflowError("Octave shift must be between -2 and +2")
            if not none:
                inv = _inventory_for(v, new_entry)
                keys = {(s["part_id"], s["staff"], s["voice"]) for s in inv["streams"]}
                if (new_entry["part_id"], new_entry["staff"], new_entry["voice"]) not in keys:
                    raise WorkflowError(f"{PART_NAMES[part]}: that part/staff/voice does not exist in the score")
                bars, flags, clef = mxi.extract_part(inv, part, new_entry)
                if bars is None:
                    raise WorkflowError(flags[0]["message"] if flags else "Mapping failed")
            else:
                bars, clef = None, None
                flags = [{"level": "info", "code": "unmapped", "part": part, "bar": None,
                          "message": f"Confirmed: this piece has no {PART_NAMES[part]} part."}]
            new_model = _replace_part(new_model, part, bars, flags, clef, new_entry["label"])
            new_mapping[part] = new_entry
            changes.append(("mapping", part, {"before": _mapping_summary({part: old})[part],
                                              "after": _mapping_summary({part: new_entry})[part],
                                              "octave_shift": new_entry["octave_shift"], "confirmed": confirm}))
        names = ", ".join(PART_NAMES[p] for p in entries)
        return _insert_version(conn, user, v["song_id"], vid, new_model, new_mapping, v["source_file"],
                               f"Mapping {'confirmed' if confirm else 'changed'}: {names}", changes)


def _same_source(a, b):
    return (a.get("part_id"), str(a.get("staff")), str(a.get("voice"))) == \
        (b.get("part_id"), str(b.get("staff")), str(b.get("voice")))


def set_label(user, vid: int, part: str, label: str) -> int:
    label = (label or "").strip()
    if not 1 <= len(label) <= 40:
        raise WorkflowError("Label must be 1 to 40 characters")
    with db.transaction() as conn:
        v, model, mapping = _editable(conn, user, vid, part)
        old = (mapping.get(part) or {}).get("label")
        new_mapping = copy.deepcopy(mapping)
        new_mapping[part]["label"] = label
        new_model = copy.deepcopy(model)
        if new_model["parts"].get(part):
            new_model["parts"][part]["label"] = label
        return _insert_version(conn, user, v["song_id"], vid, new_model, new_mapping, v["source_file"],
                               f"{PART_NAMES[part]}: label changed",
                               [("label", part, {"before": old, "after": label})])


def reupload_part(user, vid: int, part: str, filename: str, data: bytes, selection: dict | None = None) -> int:
    """Replace ONE part from a corrected MusicXML. Other parts are never read from the new file."""
    xml = load_score_upload(filename, data)
    inv = mxi.inspect(xml)
    with db.transaction() as conn:
        v, model, mapping = _editable(conn, user, vid, part)
        if [b["ticks"] for b in inv["bars"]] != [b["ticks"] for b in model["bars"]]:
            raise WorkflowError("The corrected file has a different bar structure. Only note corrections within the "
                                "existing bars can be re-uploaded; ask the director for structural changes.")
        if selection and selection.get("part_id"):
            sel = {"part_id": selection["part_id"], "staff": int(selection.get("staff") or 1),
                   "voice": str(selection.get("voice") or "1"), "octave_shift": int(selection.get("octave_shift") or 0)}
        else:
            sel = mxi.propose_mapping(inv)[part]
            if not sel.get("part_id"):
                raise WorkflowError("Could not find your part in that file by name. Choose part, staff and voice.")
        bars, flags, clef = mxi.extract_part(inv, part, sel)
        if bars is None:
            raise WorkflowError(flags[0]["message"] if flags else "Could not read your part from that file")
        src = _store(v["song_id"], "sources", "musicxml", xml)
        old = mapping.get(part) or {}
        new_entry = {**sel, "confirmed": True, "confirmed_by": user["username"],
                     "label": old.get("label") or PART_NAMES[part], "source_file": src}
        new_model = _replace_part(model, part, bars, flags, clef, new_entry["label"])
        changed = [model["bars"][i]["label"] for i in range(len(bars))
                   if model["parts"].get(part) is None or format_bar_tokens(bars[i]) !=
                   format_bar_tokens(model["parts"][part]["bars"][i])]
        new_mapping = dict(mapping)
        new_mapping[part] = new_entry
        return _insert_version(conn, user, v["song_id"], vid, new_model, new_mapping, v["source_file"],
                               f"{PART_NAMES[part]}: corrected MusicXML uploaded",
                               [("reupload", part, {"bars_changed": changed})])


# ---- Review ------------------------------------------------------------------------

def add_review_note(user, vid: int, part: str | None, bar_index: int | None, text: str) -> None:
    require_role(user, "director", "voice_lead")
    text = (text or "").strip()
    if not 1 <= len(text) <= 2000:
        raise WorkflowError("Note must be 1 to 2000 characters")
    if part is not None and part not in VOICE_PARTS:
        raise WorkflowError("Unknown voice part")
    with db.transaction() as conn:
        get_version(conn, vid)
        conn.execute("INSERT INTO review_notes (version_id, user_id, at, part, bar_index, text) VALUES (?, ?, ?, ?, ?, ?)",
                     (vid, user["id"], now_iso(), part, bar_index, text))


def readiness(conn, v) -> list[str]:
    """Reasons a version cannot go to review yet (empty list = ready)."""
    problems = []
    if v["song_kind"] == "score":
        mapping = json.loads(v["mapping_json"])
        model = json.loads(v["model_json"])
        for vp in VOICE_PARTS:
            if not (mapping.get(vp) or {}).get("confirmed"):
                problems.append(f"{PART_NAMES[vp]} mapping is not confirmed")
        for f in model["flags"]:
            if f["level"] == "error":
                problems.append(f["message"])
    if render_state(conn, v["id"]).get("status") != "done":
        problems.append("Audio is not rendered yet")
    return problems


def submit(user, vid: int) -> None:
    require_role(user, "director", "voice_lead")
    with db.transaction() as conn:
        v = get_version(conn, vid)
        if v["id"] != latest_version_id(conn, v["song_id"]):
            raise WorkflowError("Only the latest version can be submitted")
        if v["status"] not in ("draft", "rejected"):
            raise WorkflowError(f"Version is {v['status']}")
        problems = readiness(conn, v)
        if problems:
            raise WorkflowError("Not ready: " + "; ".join(problems))
        conn.execute("UPDATE versions SET status = 'in_review' WHERE id = ?", (vid,))
        conn.execute("INSERT INTO changes (version_id, user_id, at, action, part, detail_json) VALUES (?, ?, ?, "
                     "'submit', NULL, '{}')", (vid, user["id"], now_iso()))


def decide(user, vid: int, approve: bool, note: str = "") -> None:
    require_role(user, "director")
    with db.transaction() as conn:
        v = get_version(conn, vid)
        if v["id"] != latest_version_id(conn, v["song_id"]):
            raise WorkflowError("A newer version exists; review that one instead")
        if v["status"] != "in_review":
            raise WorkflowError("Only a version in review can be approved or rejected")
        if approve:
            problems = readiness(conn, v)
            if problems:
                raise WorkflowError("Not ready: " + "; ".join(problems))
            conn.execute("UPDATE versions SET status = 'superseded' WHERE song_id = ? AND status = 'approved'",
                         (v["song_id"],))
        conn.execute("UPDATE versions SET status = ?, reviewed_by = ?, reviewed_at = ?, review_decision_note = ? "
                     "WHERE id = ?", ("approved" if approve else "rejected", user["id"], now_iso(), note[:1000], vid))
        conn.execute("INSERT INTO changes (version_id, user_id, at, action, part, detail_json) VALUES (?, ?, ?, ?, "
                     "NULL, ?)", (vid, user["id"], now_iso(), "approve" if approve else "reject",
                                  json.dumps({"note": note[:1000]})))


def retry_render(user, vid: int) -> None:
    require_role(user, "director")
    with db.transaction() as conn:
        v = get_version(conn, vid)
        if v["song_kind"] != "score":
            raise WorkflowError("Nothing to render")
        state = render_state(conn, vid)
        if state.get("status") in ("queued", "running"):
            raise WorkflowError("Render already in progress")
        conn.execute("INSERT INTO jobs (version_id, kind, status, max_attempts, queued_at) VALUES (?, 'render', "
                     "'queued', ?, ?)", (vid, config.JOB_MAX_ATTEMPTS, now_iso()))


# ---- Feedback ------------------------------------------------------------------------

def add_feedback(song_id: int, bar_label: str | None, comment: str) -> None:
    """Store anonymous feedback. Deliberately takes no user argument."""
    comment = (comment or "").strip()
    if not 1 <= len(comment) <= config.FEEDBACK_MAX_CHARS:
        raise WorkflowError(f"Comment must be 1 to {config.FEEDBACK_MAX_CHARS} characters")
    bar_label = (bar_label or "").strip()[:12] or None
    iso = datetime.now(timezone.utc).isocalendar()
    with db.transaction() as conn:
        if approved_version(conn, song_id) is None:
            raise LookupError("Song not found")
        conn.execute("INSERT INTO feedback (id, song_id, bar_label, comment, week) VALUES (?, ?, ?, ?, ?)",
                     (secrets.token_hex(16), song_id, bar_label, comment, f"{iso.year}-W{iso.week:02d}"))
