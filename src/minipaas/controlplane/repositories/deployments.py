"""Acceso a `deployments`, `deployment_services` y `deployment_events`.

Estados de una revisión (`deployments.status`), distintos del estado lógico de la aplicación y
del estado real de los contenedores:

    pending -> preparing -> deploying -> healthy -> (stopped | superseded)
                    \\-> failed | rolling_back -> rolled_back | rollback_failed
    pending -> discarded (la sustituye otra revisión)   cualquier operación -> interrupted
"""

import json
import sqlite3
from dataclasses import dataclass

IN_PROGRESS = ("preparing", "deploying", "rolling_back")


@dataclass(frozen=True)
class Deployment:
    id: int
    application_id: int
    revision: int
    operation_id: str
    request_id: str
    status: str
    status_label: str
    previous_deployment_id: int | None
    previous_revision: int | None
    is_active: bool
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


@dataclass(frozen=True)
class DeploymentService:
    service_name: str
    catalog_id: str
    image_ref: str
    internal_port: int
    host_port: int | None
    env: dict[str, str]
    memory_mb: int
    cpus: float


@dataclass(frozen=True)
class DeploymentEvent:
    occurred_at: str
    step: str
    outcome: str
    message: str


_SELECT = (
    "SELECT d.id, d.application_id, d.revision, d.operation_id, d.request_id, d.status,"
    " s.description AS status_label, d.previous_deployment_id, p.revision AS previous_revision,"
    " (a.active_deployment_id = d.id) AS is_active, d.error, d.created_at, d.started_at,"
    " d.finished_at"
    " FROM deployments d JOIN deployment_statuses s ON s.code = d.status"
    " JOIN applications a ON a.id = d.application_id"
    " LEFT JOIN deployments p ON p.id = d.previous_deployment_id"
)


def _build(row: sqlite3.Row | None) -> Deployment | None:
    if row is None:
        return None
    data = dict(row)
    data["is_active"] = bool(data["is_active"])
    return Deployment(**data)


def get_by_id(conn: sqlite3.Connection, deployment_id: int) -> Deployment | None:
    return _build(conn.execute(_SELECT + " WHERE d.id = ?", (deployment_id,)).fetchone())


def get_by_revision(conn: sqlite3.Connection, app_id: int, revision: int) -> Deployment | None:
    row = conn.execute(
        _SELECT + " WHERE d.application_id = ? AND d.revision = ?", (app_id, revision)
    ).fetchone()
    return _build(row)


def get_by_request_id(conn: sqlite3.Connection, app_id: int, request_id: str) -> Deployment | None:
    row = conn.execute(
        _SELECT + " WHERE d.application_id = ? AND d.request_id = ?", (app_id, request_id)
    ).fetchone()
    return _build(row)


def list_for_app(conn: sqlite3.Connection, app_id: int) -> list[Deployment]:
    rows = conn.execute(
        _SELECT + " WHERE d.application_id = ? ORDER BY d.revision DESC", (app_id,)
    ).fetchall()
    return [_build(row) for row in rows]


def list_in_progress(conn: sqlite3.Connection) -> list[Deployment]:
    marks = ", ".join("?" * len(IN_PROGRESS))
    rows = conn.execute(_SELECT + f" WHERE d.status IN ({marks})", IN_PROGRESS).fetchall()  # noqa: S608
    return [_build(row) for row in rows]


def next_revision(conn: sqlite3.Connection, app_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(revision), 0) + 1 FROM deployments WHERE application_id = ?",
        (app_id,),
    ).fetchone()
    return row[0]


def insert_pending(
    conn: sqlite3.Connection,
    app_id: int,
    revision: int,
    operation_id: str,
    request_id: str,
    now: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO deployments (application_id, revision, operation_id, request_id, status,"
        " created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (app_id, revision, operation_id, request_id, now),
    )
    return cursor.lastrowid


def discard_pending(conn: sqlite3.Connection, app_id: int, keep_id: int, now: str) -> None:
    conn.execute(
        "UPDATE deployments SET status = 'discarded', finished_at = ?"
        " WHERE application_id = ? AND status = 'pending' AND id != ?",
        (now, app_id, keep_id),
    )


def mark_preparing(
    conn: sqlite3.Connection, deployment_id: int, previous_id: int | None, now: str
) -> bool:
    """Pasa `pending` a `preparing`. Lanza IntegrityError si ya hay otra operación en curso
    (índice único `one_operation_per_app`). False si la revisión ya no estaba `pending`."""
    cursor = conn.execute(
        "UPDATE deployments SET status = 'preparing', started_at = ?, previous_deployment_id = ?"
        " WHERE id = ? AND status = 'pending'",
        (now, previous_id, deployment_id),
    )
    return cursor.rowcount == 1


def set_status(
    conn: sqlite3.Connection,
    deployment_id: int,
    status: str,
    *,
    error: str | None = None,
    finished_at: str | None = None,
) -> None:
    conn.execute(
        "UPDATE deployments SET status = ?, error = COALESCE(?, error),"
        " finished_at = COALESCE(?, finished_at) WHERE id = ?",
        (status, error, finished_at, deployment_id),
    )


def insert_service(conn: sqlite3.Connection, deployment_id: int, s: DeploymentService) -> None:
    conn.execute(
        "INSERT INTO deployment_services (deployment_id, service_name, catalog_id, image_ref,"
        " internal_port, host_port, env, memory_mb, cpus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            deployment_id,
            s.service_name,
            s.catalog_id,
            s.image_ref,
            s.internal_port,
            s.host_port,
            json.dumps(s.env, sort_keys=True),
            s.memory_mb,
            s.cpus,
        ),
    )


def list_services(conn: sqlite3.Connection, deployment_id: int) -> list[DeploymentService]:
    rows = conn.execute(
        "SELECT service_name, catalog_id, image_ref, internal_port, host_port, env, memory_mb,"
        " cpus FROM deployment_services WHERE deployment_id = ? ORDER BY id",
        (deployment_id,),
    ).fetchall()
    return [DeploymentService(**{**dict(r), "env": json.loads(r["env"])}) for r in rows]


def add_event(
    conn: sqlite3.Connection, deployment_id: int, now: str, step: str, outcome: str, message: str
) -> None:
    conn.execute(
        "INSERT INTO deployment_events (deployment_id, occurred_at, step, outcome, message)"
        " VALUES (?, ?, ?, ?, ?)",
        (deployment_id, now, step, outcome, message),
    )


def list_events(conn: sqlite3.Connection, deployment_id: int) -> list[DeploymentEvent]:
    rows = conn.execute(
        "SELECT occurred_at, step, outcome, message FROM deployment_events"
        " WHERE deployment_id = ? ORDER BY id",
        (deployment_id,),
    ).fetchall()
    return [DeploymentEvent(**dict(row)) for row in rows]
