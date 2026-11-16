"""Concert preparation: repertoire checklist, rehearsals, notices and the choir knowledge base.

Practice progress is personal: it is stored per singer and only ever returned to that singer.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import db, workflow

TZ = ZoneInfo("Europe/Budapest")

# The choir's own four learning stages (Practice Hub guide, "Mastery Matrix").
STAGES = ["Listening to Lead", "Singing with Guide", "Singing Solo / Minus-One", "Ready for Weekend Meld"]

CONCERT = {
    "title": "10th Anniversary Christmas Concert & Thanksgiving Mass",
    "date": "2026-12-06",
    "schedule": [["14:30", "Christmas Concert"], ["16:00", "Thanksgiving Mass"], ["17:00", "Agape Fellowship"]],
}

REPERTOIRE_2026 = [
    "Baba tunaleta vipaji", "Unmerited Grace", "The grace", "Time after time", "Our father", "Nyathi onyuol",
    "Unto us a child is born", "God with us", "Otito", "We wish you a merry", "Kept by the power", "Homma yembo ose",
]

# Weekend times come from the choir's practice guide (Saturday 5-7:30 pm, Sunday from 2 pm).
# Thursday times are not decided yet, so they are stored without a time.
REHEARSALS_2026 = [
    ("2026-11-19", None, None, "thursday"),
    ("2026-11-22", "14:00", None, "weekend"),
    ("2026-11-26", None, None, "thursday"),
    ("2026-11-28", "17:00", "19:30", "weekend"),
    ("2026-11-29", "14:00", None, "weekend"),
    ("2026-12-03", None, None, "thursday"),
    ("2026-12-05", "17:00", "19:30", "weekend"),
]

CRUNCH_NOTICE = ("Looking at the number of rehearsals remaining and the amount of work we still need to put in, "
                 "we are left with no option but to start Thursday rehearsals.")


def today() -> date:
    return datetime.now(TZ).date()


def seed_concert() -> dict:
    """Insert the 2026 concert data once. Safe to run again: existing rows are kept."""
    added = {"songs": 0, "rehearsals": 0, "notices": 0}
    with db.transaction() as conn:
        for pos, title in enumerate(REPERTOIRE_2026, start=1):
            cur = conn.execute("INSERT OR IGNORE INTO repertoire (position, title) VALUES (?, ?)", (pos, title))
            added["songs"] += cur.rowcount
        for day, start, end, kind in REHEARSALS_2026:
            cur = conn.execute("INSERT OR IGNORE INTO rehearsals (day, start_time, end_time, kind) VALUES (?, ?, ?, ?)",
                               (day, start, end, kind))
            added["rehearsals"] += cur.rowcount
        if not conn.execute("SELECT 1 FROM notices WHERE text = ?", (CRUNCH_NOTICE,)).fetchone():
            conn.execute("INSERT INTO notices (level, text, active) VALUES ('urgent', ?, 1)", (CRUNCH_NOTICE,))
            added["notices"] = 1
    return added


def streak(conn, user_id: int) -> int:
    """Consecutive practice days ending today, or yesterday if today is not logged yet."""
    days = {r["day"] for r in conn.execute("SELECT day FROM practice_days WHERE user_id = ?", (user_id,))}
    d = today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def dashboard(user: dict) -> dict:
    now = today().isoformat()
    with db.closing() as conn:
        notices = [dict(r) for r in conn.execute("SELECT id, level, text FROM notices WHERE active = 1 ORDER BY id")]
        rehearsals = [dict(r) for r in conn.execute(
            "SELECT r.id, r.day, r.start_time, r.end_time, r.kind, r.note, a.rsvp AS my_rsvp "
            "FROM rehearsals r LEFT JOIN attendance a ON a.rehearsal_id = r.id AND a.user_id = ? "
            "WHERE r.day >= ? AND r.cancelled = 0 ORDER BY r.day, r.start_time", (user["id"], now))]
        songs = []
        for r in conn.execute(
                "SELECT p.id, p.position, p.title, p.song_id, COALESCE(g.stage, 0) AS stage FROM repertoire p "
                "LEFT JOIN practice_progress g ON g.repertoire_id = p.id AND g.user_id = ? ORDER BY p.position",
                (user["id"],)):
            approved = workflow.approved_version(conn, r["song_id"]) if r["song_id"] else None
            songs.append({"id": r["id"], "position": r["position"], "title": r["title"], "stage": r["stage"],
                          "practise_version_id": approved["id"] if approved else None})
        days_left = (date.fromisoformat(CONCERT["date"]) - today()).days
        return {"concert": {**CONCERT, "days_left": days_left}, "notices": notices, "rehearsals": rehearsals,
                "songs": songs, "stages": STAGES, "streak": streak(conn, user["id"])}


def set_stage(user: dict, repertoire_id: int, stage: int) -> dict:
    if not 0 <= stage <= len(STAGES):
        raise ValueError("Unknown stage")
    with db.transaction() as conn:
        if not conn.execute("SELECT 1 FROM repertoire WHERE id = ?", (repertoire_id,)).fetchone():
            raise LookupError("Song not found")
        conn.execute("INSERT INTO practice_progress (user_id, repertoire_id, stage) VALUES (?, ?, ?) "
                     "ON CONFLICT (user_id, repertoire_id) DO UPDATE SET stage = excluded.stage",
                     (user["id"], repertoire_id, stage))
        if stage > 0:  # un-ticking does not count as a practice day
            conn.execute("INSERT OR IGNORE INTO practice_days (user_id, day) VALUES (?, ?)",
                         (user["id"], today().isoformat()))
        return {"stage": stage, "streak": streak(conn, user["id"])}


def set_rsvp(user: dict, rehearsal_id: int, rsvp: str) -> None:
    with db.transaction() as conn:
        if not conn.execute("SELECT 1 FROM rehearsals WHERE id = ? AND cancelled = 0", (rehearsal_id,)).fetchone():
            raise LookupError("Rehearsal not found")
        conn.execute("INSERT INTO attendance (rehearsal_id, user_id, rsvp) VALUES (?, ?, ?) "
                     "ON CONFLICT (rehearsal_id, user_id) DO UPDATE SET rsvp = excluded.rsvp",
                     (rehearsal_id, user["id"], rsvp))


# ---- Knowledge base (full-text search over the choir's documents) ---------------------------------

_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_WORD = re.compile(r"\w+", re.UNICODE)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split a Markdown/plain-text document into (heading, body) sections."""
    sections, heading, lines = [], "", []
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            if "".join(lines).strip():
                sections.append((heading, "\n".join(lines).strip()))
            heading, lines = m.group(1).strip(), []
        else:
            lines.append(line)
    if "".join(lines).strip():
        sections.append((heading, "\n".join(lines).strip()))
    return sections


def kb_upsert(source_id: str, title: str, url: str | None, text: str) -> int:
    """Replace one document's sections. Returns the number of sections stored."""
    sections = split_sections(text)
    with db.transaction() as conn:
        old = conn.execute("SELECT id FROM kb_docs WHERE source_id = ?", (source_id,)).fetchone()
        if old:
            conn.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (old["id"],))
            conn.execute("UPDATE kb_docs SET title = ?, url = ?, synced_at = ? WHERE id = ?",
                         (title, url, workflow.now_iso(), old["id"]))
            doc_id = old["id"]
        else:
            doc_id = conn.execute("INSERT INTO kb_docs (source_id, title, url, synced_at) VALUES (?, ?, ?, ?)",
                                  (source_id, title, url, workflow.now_iso())).lastrowid
        conn.executemany("INSERT INTO kb_chunks (doc_id, heading, body) VALUES (?, ?, ?)",
                         [(doc_id, h, b) for h, b in sections])
    return len(sections)


def kb_import_dir(folder: Path) -> list[tuple[str, int]]:
    out = []
    for path in sorted(folder.glob("*")):
        if path.suffix.lower() in (".md", ".txt") and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            first = next((ln for ln in text.splitlines() if ln.strip()), path.stem)
            title = _HEADING.sub(r"\1", first).strip()[:120] or path.stem
            out.append((path.name, kb_upsert(f"file:{path.name}", title, None, text)))
    return out


def kb_search(query: str, limit: int = 8) -> list[dict]:
    words = _WORD.findall(query)[:12]
    if not words:
        return []
    # Each word is quoted, so user input can never be read as FTS query syntax.
    match = " OR ".join(f'"{w}"*' for w in words)
    with db.closing() as conn:
        rows = conn.execute(
            "SELECT d.title, d.url, c.heading, snippet(kb_chunks, 2, '[[', ']]', ' … ', 28) AS snippet "
            "FROM kb_chunks c JOIN kb_docs d ON d.id = c.doc_id WHERE kb_chunks MATCH ? "
            "ORDER BY bm25(kb_chunks) LIMIT ?", (match, limit)).fetchall()
    return [dict(r) for r in rows]
