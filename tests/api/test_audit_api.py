import json

from conftest import PASSWORD, USERNAME


def events(query):
    return query("SELECT * FROM audit_events ORDER BY id")


def summary(query):
    return [(e["event_type"], e["outcome"]) for e in events(query)]


def test_full_flow_events_and_no_secrets(client, app, admin, query):
    client.post("/api/auth/login", json={"username": USERNAME, "password": "mala-contraseña-1"})
    login = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    csrf, cookie = login.json()["csrf_token"], client.cookies["minipaas_session"]
    headers = {"X-CSRF-Token": csrf}
    client.post("/api/applications", json={"name": "Demo", "slug": "demo"}, headers=headers)
    client.patch("/api/applications/demo", json={"description": "d"}, headers=headers)
    client.delete("/api/applications/demo", headers=headers)
    client.post("/api/auth/logout", headers=headers)

    assert summary(query) == [
        ("database.migrate", "success"),
        ("admin.create", "success"),
        ("auth.login_failed", "failure"),
        ("auth.login", "success"),
        ("application.create", "success"),
        ("application.update", "success"),
        ("application.delete", "success"),
        ("auth.logout", "success"),
    ]
    by_type = {e["event_type"]: e for e in events(query)}
    user_id = query("SELECT id FROM users")[0]["id"]
    failed = by_type["auth.login_failed"]
    assert failed["user_id"] is None and json.loads(failed["metadata"]) == {
        "reason": "invalid_credentials"
    }
    assert USERNAME not in repr(failed)
    for kind in (
        "auth.login",
        "auth.logout",
        "application.create",
        "application.update",
        "application.delete",
    ):
        assert by_type[kind]["user_id"] == user_id and by_type[kind]["client_ip"] == "testclient"
    assert by_type["application.create"]["resource_id"] == "demo"
    assert json.loads(by_type["application.update"]["metadata"]) == {"fields": "description"}
    assert json.loads(by_type["admin.create"]["metadata"]) == {"source": "test"}

    dump = repr(events(query))
    for secret in (PASSWORD, "mala-contraseña-1", cookie, csrf):
        assert secret not in dump


def test_failures_do_not_leave_success_events(logged_in, query):
    client, headers = logged_in.client, logged_in.headers
    client.post("/api/applications", json={"name": "A", "slug": "repetida"}, headers=headers)
    client.post("/api/applications", json={"name": "B", "slug": "repetida"}, headers=headers)
    client.patch("/api/applications/nada", json={"name": "x"}, headers=headers)
    client.delete("/api/applications/nada", headers=headers)
    assert [e for e in summary(query) if e[0].startswith("application.")] == [
        ("application.create", "success"),
        ("application.create", "failure"),
        ("application.update", "failure"),
        ("application.delete", "failure"),
    ]


def test_rate_limited_attempt_is_audited(client, admin, query):
    for _ in range(6):
        client.post("/api/auth/login", json={"username": USERNAME, "password": "mala-contraseña-1"})
    reasons = [
        json.loads(e["metadata"])["reason"]
        for e in events(query)
        if e["event_type"] == "auth.login_failed"
    ]
    assert reasons == ["invalid_credentials"] * 5 + ["rate_limited"]


def test_failed_admin_create_is_audited(app, admin, query):
    import pytest

    from minipaas.controlplane.services.auth import AdminAlreadyExists

    conn = app.state.db.connect()
    with pytest.raises(AdminAlreadyExists):
        app.state.auth.create_admin(conn, "otro", PASSWORD, "cli")
    conn.close()
    assert summary(query)[-1] == ("admin.create", "failure")
    assert query("SELECT COUNT(*) AS n FROM users")[0]["n"] == 1


def test_get_requests_create_no_events(logged_in, query):
    before = len(events(query))
    for _ in range(3):
        logged_in.client.get("/api/applications")
        logged_in.client.get("/api/auth/session")
    assert len(events(query)) == before


def test_success_event_rolls_back_with_failed_operation(app, admin, query):
    """Si la operación falla tras escribir el evento, el rollback elimina también el evento."""
    import pytest

    from minipaas.controlplane.db.connection import transaction
    from minipaas.controlplane.services import audit

    conn = app.state.db.connect()
    before = len(events(query))
    with pytest.raises(RuntimeError), transaction(conn):
        app.state.applications.audit.record(conn, audit.APPLICATION_CREATE, audit.SUCCESS)
        raise RuntimeError("la operación falló")
    conn.close()
    assert len(events(query)) == before
