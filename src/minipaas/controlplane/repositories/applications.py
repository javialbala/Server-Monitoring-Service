"""Acceso a la tabla `applications`.

`create` deja propagar `sqlite3.IntegrityError` si el slug ya existe: la restricción UNIQUE
de la base de datos es la única comprobación fiable (comprobar antes y insertar después
tendría una condición de carrera).
"""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Application:
    id: int
    slug: str
    name: str
    description: str
    status: str
    status_label: str
    created_at: str
    updated_at: str


_SELECT = (
    "SELECT a.id, a.slug, a.name, a.description, a.status, s.description AS status_label,"
    " a.created_at, a.updated_at"
    " FROM applications a JOIN application_statuses s ON s.code = a.status"
)


def list_all(conn: sqlite3.Connection) -> list[Application]:
    rows = conn.execute(_SELECT + " ORDER BY a.created_at DESC, a.id DESC").fetchall()
    return [Application(**dict(row)) for row in rows]


def get_by_slug(conn: sqlite3.Connection, slug: str) -> Application | None:
    row = conn.execute(_SELECT + " WHERE a.slug = ?", (slug,)).fetchone()
    return Application(**dict(row)) if row else None


def create(
    conn: sqlite3.Connection, slug: str, name: str, description: str, now: str
) -> Application:
    conn.execute(
        "INSERT INTO applications (slug, name, description, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (slug, name, description, now, now),
    )
    return get_by_slug(conn, slug)


def update(
    conn: sqlite3.Connection, slug: str, name: str, description: str, now: str
) -> Application | None:
    conn.execute(
        "UPDATE applications SET name = ?, description = ?, updated_at = ? WHERE slug = ?",
        (name, description, now, slug),
    )
    return get_by_slug(conn, slug)


def delete(conn: sqlite3.Connection, slug: str) -> bool:
    return conn.execute("DELETE FROM applications WHERE slug = ?", (slug,)).rowcount > 0
