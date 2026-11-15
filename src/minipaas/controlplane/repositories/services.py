"""Acceso a la tabla `services` (configuración editable de los servicios de una aplicación)."""

import json
import sqlite3
from dataclasses import dataclass

from minipaas.common.catalog import HOST_PORT_MAX, HOST_PORT_MIN


@dataclass(frozen=True)
class Service:
    id: int
    application_id: int
    name: str
    catalog_id: str
    internal_port: int
    host_port: int | None
    env: dict[str, str]
    memory_mb: int
    cpus: float
    created_at: str
    updated_at: str


def _build(row: sqlite3.Row) -> Service:
    data = dict(row)
    data["env"] = json.loads(data["env"])
    return Service(**data)


def list_for_app(conn: sqlite3.Connection, app_id: int) -> list[Service]:
    rows = conn.execute(
        "SELECT * FROM services WHERE application_id = ? ORDER BY id", (app_id,)
    ).fetchall()
    return [_build(row) for row in rows]


def get(conn: sqlite3.Connection, app_id: int, name: str) -> Service | None:
    row = conn.execute(
        "SELECT * FROM services WHERE application_id = ? AND name = ?", (app_id, name)
    ).fetchone()
    return _build(row) if row else None


def insert(
    conn: sqlite3.Connection,
    app_id: int,
    name: str,
    catalog_id: str,
    internal_port: int,
    host_port: int | None,
    env: dict[str, str],
    memory_mb: int,
    cpus: float,
    now: str,
) -> None:
    conn.execute(
        "INSERT INTO services (application_id, name, catalog_id, internal_port, host_port, env,"
        " memory_mb, cpus, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            app_id,
            name,
            catalog_id,
            internal_port,
            host_port,
            json.dumps(env, sort_keys=True),
            memory_mb,
            cpus,
            now,
            now,
        ),
    )


def update(
    conn: sqlite3.Connection,
    service_id: int,
    internal_port: int,
    host_port: int | None,
    env: dict[str, str],
    memory_mb: int,
    cpus: float,
    now: str,
) -> None:
    conn.execute(
        "UPDATE services SET internal_port = ?, host_port = ?, env = ?, memory_mb = ?, cpus = ?,"
        " updated_at = ? WHERE id = ?",
        (
            internal_port,
            host_port,
            json.dumps(env, sort_keys=True),
            memory_mb,
            cpus,
            now,
            service_id,
        ),
    )


def delete(conn: sqlite3.Connection, service_id: int) -> None:
    conn.execute("DELETE FROM services WHERE id = ?", (service_id,))


def reserved_ports(conn: sqlite3.Connection, app_id: int, own_service_id: int | None) -> set[int]:
    """Puertos del host que NO puede usar un servicio de `app_id`.

    Son los de cualquier otro servicio (la columna es UNIQUE) y los de los servicios de la
    revisión ACTIVA de otra aplicación (siguen ocupados en el host aunque se editen o se
    borren los servicios editables).
    """
    rows = conn.execute(
        "SELECT host_port FROM services WHERE host_port IS NOT NULL AND id IS NOT ?"
        " UNION "
        "SELECT ds.host_port FROM deployment_services ds"
        " JOIN applications a ON a.active_deployment_id = ds.deployment_id"
        " WHERE ds.host_port IS NOT NULL AND a.id != ?",
        (own_service_id, app_id),
    ).fetchall()
    return {row[0] for row in rows}


def first_free_port(reserved: set[int]) -> int | None:
    return next((p for p in range(HOST_PORT_MIN, HOST_PORT_MAX + 1) if p not in reserved), None)
