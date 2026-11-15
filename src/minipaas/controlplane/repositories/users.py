"""Acceso a la tabla `users` (SQL explícito, sin ORM)."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    created_at: str
    updated_at: str


def _to_user(row: sqlite3.Row) -> User:
    return User(**dict(row))


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_by_username(conn: sqlite3.Connection, username: str) -> User | None:
    # La columna es COLLATE NOCASE: la búsqueda ya ignora mayúsculas.
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _to_user(row) if row else None


def get_by_id(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _to_user(row) if row else None


def create(conn: sqlite3.Connection, username: str, password_hash: str, now: str) -> User:
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, now, now),
    )
    return User(cursor.lastrowid, username, password_hash, now, now)


def update_password_hash(conn: sqlite3.Connection, user_id: int, password_hash: str, now: str):
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (password_hash, now, user_id),
    )
