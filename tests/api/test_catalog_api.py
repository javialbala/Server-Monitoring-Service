from conftest import make_app, make_settings
from fastapi.testclient import TestClient

ITEM_FIELDS = {
    "id", "name", "description", "version", "repository", "digest", "architectures",
    "internal_ports", "default_internal_port", "publishable", "env", "memory_mb", "cpus",
    "license", "source", "limitations", "test_only",
}  # fmt: skip


def test_requires_session(client):
    assert client.get("/api/catalog").status_code == 401


def test_catalog_without_test_entries(api):
    items = api.get("/api/catalog").json()["items"]
    assert {i["id"] for i in items} == {"nginx-static", "whoami"}
    assert set(items[0]) == ITEM_FIELDS
    whoami = next(i for i in items if i["id"] == "whoami")
    assert whoami["env"][0].keys() == {"name", "label", "help", "pattern", "max_length"}
    assert whoami["memory_mb"] == {"default": 32, "min": 16, "max": 128}
    assert whoami["cpus"] == {"default": 0.25, "min": 0.1, "max": 0.5}
    assert whoami["digest"].startswith("sha256:") and not whoami["test_only"]


def test_catalog_does_not_expose_docker_options(api):
    text = api.get("/api/catalog").text
    for private in ("pids_limit", "tmpfs", "user"):
        assert private not in text


def test_catalog_with_test_entries(tmp_path, clock, admin_login=None):
    from conftest import PASSWORD, USERNAME

    app = make_app(make_settings(tmp_path, enable_test_catalog=True), clock)
    with TestClient(app) as client:
        conn = app.state.db.connect()
        app.state.auth.create_admin(conn, USERNAME, PASSWORD, source="test")
        conn.close()
        client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        items = client.get("/api/catalog").json()["items"]
    assert {i["id"] for i in items if i["test_only"]} == {"test-crash", "test-unhealthy"}
    assert len(items) == 4
