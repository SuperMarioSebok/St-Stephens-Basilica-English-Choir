"""Passwords (scrypt), opaque session tokens and login throttling."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from . import config, db

_failures: dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def locked_out(username: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(username.lower(), []) if now - t < config.LOGIN_LOCK_SECONDS]
    _failures[username.lower()] = recent
    return len(recent) >= config.LOGIN_MAX_FAILURES


def login(username: str, password: str) -> str | None:
    if locked_out(username):
        return None
    with db.closing() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE username = ? AND active = 1",
                           (username,)).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            _failures.setdefault(username.lower(), []).append(time.time())
            return None
        token = secrets.token_urlsafe(32)
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                     (_token_hash(token), row["id"], int(time.time()) + config.SESSION_DAYS * 86400))
    _failures.pop(username.lower(), None)
    return token


def user_for_token(token: str | None):
    if not token:
        return None
    with db.closing() as conn:
        return conn.execute(
            "SELECT u.id, u.username, u.display_name, u.role, u.voice_part FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1",
            (_token_hash(token), int(time.time()))).fetchone()


def logout(token: str | None) -> None:
    if token:
        with db.closing() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def create_user(username: str, password: str, role: str, voice_part: str | None = None,
                display_name: str | None = None) -> int:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    with db.closing() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, display_name, password_hash, role, voice_part) VALUES (?, ?, ?, ?, ?)",
            (username, display_name or username, hash_password(password), role, voice_part))
        return cur.lastrowid
