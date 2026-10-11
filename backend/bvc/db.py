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
    role TEXT NOT NULL CHECK (role IN ('singer', 'voice_lead', 'director')),
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
        conn.executescript(SCHEMA)


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
