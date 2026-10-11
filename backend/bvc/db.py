"""SQLite storage. One file, no server."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('singer', 'voice_lead', 'director', 'welcome', 'comms')),
    voice_part TEXT CHECK (voice_part IN ('S', 'A', 'T', 'B')),
    active INTEGER NOT NULL DEFAULT 1,
    CHECK (role != 'voice_lead' OR voice_part IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('score', 'manual')),
    rights_note TEXT NOT NULL,
    is_test_piece INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

-- Versions are immutable once written. Every change creates a new row.
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY,
    song_id INTEGER NOT NULL REFERENCES songs(id),
    number INTEGER NOT NULL,
    parent_id INTEGER REFERENCES versions(id),
    status TEXT NOT NULL CHECK (status IN ('draft', 'in_review', 'approved', 'rejected', 'revoked', 'superseded')),
    source_file TEXT,
    mapping_json TEXT,
    model_json TEXT,
    manual_json TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TEXT,
    review_decision_note TEXT,
    UNIQUE (song_id, number)
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    at TEXT NOT NULL,
    action TEXT NOT NULL,
    part TEXT,
    detail_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_notes (
    id INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    at TEXT NOT NULL,
    part TEXT,
    bar_index INTEGER,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL,
    error TEXT,
    queued_at TEXT NOT NULL,
    started_at REAL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,               -- random, unguessable; still access-checked
    version_id INTEGER NOT NULL REFERENCES versions(id),
    kind TEXT NOT NULL,                -- stem | mix | score | source_audio | pdf
    part TEXT,                         -- S/A/T/B for stems; mix name for mixes
    tempo INTEGER,                     -- percent
    rel_path TEXT NOT NULL,
    mime TEXT NOT NULL,
    seconds REAL
);

-- Anonymous feedback: deliberately NO user id, NO session, NO exact timestamp,
-- NO version id (song level only, so it cannot be tied to who could see which draft).
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,               -- random, so row order reveals nothing
    song_id INTEGER NOT NULL REFERENCES songs(id),
    bar_label TEXT,
    comment TEXT NOT NULL,
    week TEXT NOT NULL                 -- ISO week only, e.g. 2026-W41
);

-- ---- Community: public page, enquiries, events, reservations, invites, survey, KPIs ----

CREATE TABLE IF NOT EXISTS site_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,           -- ISO 8601 with offset, Europe/Budapest local time
    venue TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_public INTEGER NOT NULL DEFAULT 0,
    rsvp_open INTEGER NOT NULL DEFAULT 0,
    capacity INTEGER,
    actual_attendance INTEGER,         -- entered after the event (headcount)
    donations_reported_huf INTEGER,    -- total reported by the parish or charity; the choir handles no money
    reservations_final INTEGER,        -- kept after reservation details are deleted
    created_at TEXT NOT NULL
);

-- People who filled in the public interest form. Deleted 6 months after the last status change.
CREATE TABLE IF NOT EXISTS enquiries (
    id TEXT PRIMARY KEY,
    created_on TEXT NOT NULL,
    first_name TEXT NOT NULL,
    contact TEXT NOT NULL,
    interests TEXT NOT NULL,           -- JSON list: sing, volunteer, support, concert
    voice_type TEXT,
    message TEXT NOT NULL DEFAULT '',
    under_18 INTEGER NOT NULL DEFAULT 0,
    guardian_name TEXT,
    guardian_contact TEXT,
    updates_opt_in INTEGER NOT NULL DEFAULT 0,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    notes TEXT NOT NULL DEFAULT '',
    status_changed_on TEXT NOT NULL
);

-- Status history for weekly counts. 'ref' is a random id with no link back once the enquiry is deleted.
CREATE TABLE IF NOT EXISTS enquiry_events (
    id INTEGER PRIMARY KEY,
    ref TEXT NOT NULL,
    status TEXT NOT NULL,
    on_date TEXT NOT NULL,
    interests TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    contact TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    updates_opt_in INTEGER NOT NULL DEFAULT 0,
    source TEXT,
    cancel_hash TEXT NOT NULL,
    created_on TEXT NOT NULL,
    cancelled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    voice_part TEXT,
    enquiry_id TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
);

-- Member survey (e.g. NPS). Answers carry no user id; 'survey_voters' only records THAT someone answered.
CREATE TABLE IF NOT EXISTS surveys (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    question TEXT NOT NULL,
    is_open INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS survey_voters (
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    voter_hash TEXT NOT NULL,
    PRIMARY KEY (survey_id, voter_hash)
);
CREATE TABLE IF NOT EXISTS survey_answers (
    id TEXT PRIMARY KEY,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 10),
    comment TEXT NOT NULL DEFAULT ''
);

-- Numbers typed in each Friday (followers, members). No personal data.
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id INTEGER PRIMARY KEY,
    week TEXT NOT NULL,
    metric TEXT NOT NULL,
    value INTEGER NOT NULL,
    UNIQUE (week, metric)
);
"""


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with closing() as conn:
        _migrate_roles(conn)
        conn.executescript(SCHEMA)


def _migrate_roles(conn) -> None:
    """Databases created before the 'welcome' and 'comms' roles existed get their users table rebuilt."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
    if row is None or "'welcome'" in row[0]:
        return
    users_body = SCHEMA.split("CREATE TABLE IF NOT EXISTS users", 1)[1].split(";", 1)[0]
    conn.executescript(
        "PRAGMA foreign_keys = OFF; PRAGMA legacy_alter_table = ON; BEGIN;"
        "ALTER TABLE users RENAME TO users_old;"
        f"CREATE TABLE users {users_body};"
        "INSERT INTO users SELECT * FROM users_old; DROP TABLE users_old; COMMIT;"
        "PRAGMA legacy_alter_table = OFF; PRAGMA foreign_keys = ON;")


@contextmanager
def closing():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
