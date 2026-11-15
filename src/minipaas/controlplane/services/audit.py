"""Registro de auditoría: qué pasó, quién lo hizo y con qué resultado (nunca secretos).

Regla de atomicidad: los eventos de ÉXITO se escriben dentro de la MISMA transacción que la
operación (si la operación falla, el rollback elimina también el evento); los de FALLO se
escriben en una transacción aparte, después del rollback. Así nunca queda un "success" de una
operación que no llegó a ocurrir.
"""

import json
import sqlite3

from minipaas.controlplane.clock import Clock, to_iso, utc_now
from minipaas.controlplane.repositories import audit as repo

LOGIN = "auth.login"
LOGIN_FAILED = "auth.login_failed"
LOGOUT = "auth.logout"
ADMIN_CREATE = "admin.create"
APPLICATION_CREATE = "application.create"
APPLICATION_UPDATE = "application.update"
APPLICATION_DELETE = "application.delete"
DATABASE_MIGRATE = "database.migrate"

SUCCESS = "success"
FAILURE = "failure"

FORBIDDEN_KEY_PARTS = ("password", "token", "csrf", "cookie", "secret", "authorization", "session")
MAX_TEXT_LENGTH = 200


def _validate_metadata(metadata: dict) -> None:
    """Un metadato inválido es un error de programación: debe fallar en los tests."""
    for key, value in metadata.items():
        if any(part in key.lower() for part in FORBIDDEN_KEY_PARTS):
            raise ValueError(f"Clave de auditoría prohibida (posible secreto): {key!r}")
        if not isinstance(value, str | int | bool | type(None)):
            raise ValueError(f"El metadato {key!r} debe ser un valor escalar")
        if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"El metadato {key!r} supera {MAX_TEXT_LENGTH} caracteres")


class AuditService:
    def __init__(self, clock: Clock = utc_now) -> None:
        self.clock = clock

    def record(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        outcome: str,
        *,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        client_ip: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        metadata = metadata or {}
        _validate_metadata(metadata)
        repo.insert(
            conn,
            to_iso(self.clock()),
            event_type,
            outcome,
            user_id,
            resource_type,
            resource_id,
            client_ip,
            json.dumps(metadata, sort_keys=True),
        )
