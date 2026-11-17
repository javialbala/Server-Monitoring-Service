from conftest import CONTAINERS, METRICS

PROTECTED = ["/api/metrics", "/api/containers"]


def test_health_is_public(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_data_routes_require_session(client):
    for path in PROTECTED:
        assert client.get(path).status_code == 401


def test_data_routes_forward_agent_json(client, csrf):
    assert client.get("/api/metrics").json() == METRICS
    assert client.get("/api/containers").json() == CONTAINERS


def test_agent_failure_is_502(client, csrf, agent):
    agent.down = True
    for path in PROTECTED:
        response = client.get(path)
        assert response.status_code == 502
        assert response.json() == {"detail": "El agente no responde"}


def test_after_logout_data_is_not_available(client, csrf):
    client.post("/api/logout", headers={"X-CSRF-Token": csrf})
    assert client.get("/api/metrics").status_code == 401


def test_static_files_are_served_with_csp(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Server Monitoring Service" in page.text
    assert page.headers["Content-Security-Policy"] == "default-src 'self'"
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/js/app.js").status_code == 200
    assert "no-store" in client.get("/api/session").headers["Cache-Control"]


def test_static_files_must_be_revalidated(client):
    response = client.get("/js/app.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert "etag" in response.headers
