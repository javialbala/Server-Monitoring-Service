"""Acceso a la tabla `audit_events`. Es solo de añadir: no hay UPDATE ni DELETE."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEvent:
    id: int
    occurred_at: str
    event_type: str
    outcome: str
    user_id: int | None
    resource_type: str | None
    resource_id: str | None
    client_ip: str | None
    metadata: str  # JSON


def insert(
    conn: sqlite3.Connection,
    occurred_at: str,
    event_type: str,
    outcome: str,
    user_id: int | None,
    resource_type: str | None,
    resource_id: str | None,
    client_ip: str | None,
    metadata_json: str,
) -> None:
    conn.execute(
        "INSERT INTO audit_events (occurred_at, event_type, outcome, user_id, resource_type,"
        " resource_id, client_ip, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            occurred_at,
            event_type,
            outcome,
            user_id,
            resource_type,
            resource_id,
            client_ip,
            metadata_json,
        ),
    )


def list_recent(conn: sqlite3.Connection, limit: int = 100) -> list[AuditEvent]:
    rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [AuditEvent(**dict(row)) for row in rows]
