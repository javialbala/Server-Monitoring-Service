from conftest import PASSWORD, USERNAME, make_app
from fastapi.testclient import TestClient


def test_data_and_session_survive_app_restart(settings, clock):
    with TestClient(make_app(settings, clock)) as first:
        conn = first.app.state.db.connect()
        first.app.state.auth.create_admin(conn, USERNAME, PASSWORD, "test")
        conn.close()
        login = first.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        csrf = login.json()["csrf_token"]
        cookie = first.cookies["minipaas_session"]
        first.post(
            "/api/applications", json={"name": "Persistente"}, headers={"X-CSRF-Token": csrf}
        )

    with TestClient(make_app(settings, clock)) as second:  # "reinicio": nueva app, mismo archivo
        second.cookies.set("minipaas_session", cookie)
        assert second.get("/api/applications/persistente").status_code == 200
        assert second.get("/api/auth/me").json()["username"] == USERNAME
        events = (
            second.app.state.db.connect()
            .execute("SELECT COUNT(*) FROM audit_events WHERE event_type = 'database.migrate'")
            .fetchone()[0]
        )
        assert events == 1  # el segundo arranque no aplica migraciones, así que no audita nada
