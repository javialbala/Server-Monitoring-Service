"""Acceso a la tabla `sessions`."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    id: int
    token_hash: str
    user_id: int
    csrf_token: str
    created_at: str
    last_seen_at: str
    expires_at: str
    revoked_at: str | None


def get_by_token_hash(conn: sqlite3.Connection, token_hash: str) -> Session | None:
    row = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
    return Session(**dict(row)) if row else None


def create(
    conn: sqlite3.Connection,
    token_hash: str,
    user_id: int,
    csrf_token: str,
    now: str,
    expires_at: str,
) -> Session:
    cursor = conn.execute(
        "INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, last_seen_at,"
        " expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (token_hash, user_id, csrf_token, now, now, expires_at),
    )
    return Session(cursor.lastrowid, token_hash, user_id, csrf_token, now, now, expires_at, None)


def touch(conn: sqlite3.Connection, session_id: int, now: str) -> None:
    conn.execute("UPDATE sessions SET last_seen_at = ? WHERE id = ?", (now, session_id))


def revoke(conn: sqlite3.Connection, session_id: int, now: str) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL", (now, session_id)
    )


def revoke_all_for_user(conn: sqlite3.Connection, user_id: int, now: str) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (now, user_id),
    )


def delete_old(conn: sqlite3.Connection, cutoff: str) -> int:
    """Borra las sesiones caducadas o revocadas antes de `cutoff`."""
    cursor = conn.execute(
        "DELETE FROM sessions WHERE expires_at < ? OR revoked_at < ?", (cutoff, cutoff)
    )
    return cursor.rowcount
