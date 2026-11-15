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
    active_deployment_id: int | None
    active_revision: int | None
    operation_in_progress: bool


_SELECT = (
    "SELECT a.id, a.slug, a.name, a.description, a.status, s.description AS status_label,"
    " a.created_at, a.updated_at, a.active_deployment_id, d.revision AS active_revision,"
    " EXISTS (SELECT 1 FROM deployments o WHERE o.application_id = a.id"
    "  AND o.status IN ('preparing', 'deploying', 'rolling_back')) AS operation_in_progress"
    " FROM applications a JOIN application_statuses s ON s.code = a.status"
    " LEFT JOIN deployments d ON d.id = a.active_deployment_id"
)


def _build(row: sqlite3.Row) -> Application:
    data = dict(row)
    data["operation_in_progress"] = bool(data["operation_in_progress"])
    return Application(**data)


def list_all(conn: sqlite3.Connection) -> list[Application]:
    rows = conn.execute(_SELECT + " ORDER BY a.created_at DESC, a.id DESC").fetchall()
    return [_build(row) for row in rows]


def get_by_slug(conn: sqlite3.Connection, slug: str) -> Application | None:
    row = conn.execute(_SELECT + " WHERE a.slug = ?", (slug,)).fetchone()
    return _build(row) if row else None


def get_by_id(conn: sqlite3.Connection, app_id: int) -> Application | None:
    row = conn.execute(_SELECT + " WHERE a.id = ?", (app_id,)).fetchone()
    return _build(row) if row else None


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


def set_status(conn: sqlite3.Connection, app_id: int, status: str, now: str) -> None:
    """Cambia el estado lógico (`draft`, `running`, `stopped` o `attention`)."""
    conn.execute(
        "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?", (status, now, app_id)
    )


def set_active_deployment(
    conn: sqlite3.Connection, app_id: int, deployment_id: int, status: str, now: str
) -> None:
    conn.execute(
        "UPDATE applications SET active_deployment_id = ?, status = ?, updated_at = ? WHERE id = ?",
        (deployment_id, status, now, app_id),
    )
