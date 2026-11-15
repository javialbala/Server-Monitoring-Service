import json

import pytest

from minipaas.controlplane.repositories import audit as audit_repo
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService


def test_records_event_with_json_metadata(conn, clock):
    AuditService(clock).record(
        conn,
        audit.APPLICATION_CREATE,
        audit.SUCCESS,
        resource_type="application",
        resource_id="mi-app",
        client_ip="1.2.3.4",
        metadata={"fields": "name", "count": 2, "ok": True, "nada": None},
    )
    event = audit_repo.list_recent(conn)[0]
    assert event.event_type == "application.create" and event.outcome == "success"
    assert event.occurred_at == "2030-01-01T12:00:00+00:00"
    assert json.loads(event.metadata) == {"fields": "name", "count": 2, "ok": True, "nada": None}


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "Password_hash",
        "csrf_token",
        "cookie",
        "client_secret",
        "Authorization",
        "session_id",
        "token",
    ],
)
def test_forbidden_metadata_keys(conn, key):
    with pytest.raises(ValueError, match="prohibida"):
        AuditService().record(conn, audit.LOGIN, audit.SUCCESS, metadata={key: "x"})


def test_metadata_must_be_scalar_and_short(conn):
    service = AuditService()
    with pytest.raises(ValueError, match="escalar"):
        service.record(conn, audit.LOGIN, audit.SUCCESS, metadata={"a": ["lista"]})
    with pytest.raises(ValueError, match="200"):
        service.record(conn, audit.LOGIN, audit.SUCCESS, metadata={"a": "x" * 201})
    assert audit_repo.list_recent(conn) == []
