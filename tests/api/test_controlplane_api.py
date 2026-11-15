import httpx
from fastapi.testclient import TestClient

from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.main import create_app


def make_client(handler) -> TestClient:
    agent = AgentClient("http://agent:8001", "t" * 40, transport=httpx.MockTransport(handler))
    return TestClient(create_app(agent))


def agent_ok(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer " + "t" * 40
    return httpx.Response(
        200, json={"status": "ok", "docker": {"reachable": True, "server_version": "29.0.0"}}
    )


def test_health_ok():
    response = make_client(agent_ok).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "agent": {"reachable": True},
        "docker": {"reachable": True},
    }


def test_health_does_not_expose_versions():
    assert "29.0.0" not in make_client(agent_ok).get("/api/health").text


def test_agent_down():
    def handler(request):
        raise httpx.ConnectError("sin conexión")

    response = make_client(handler).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["agent"]["reachable"] is False
    assert body["docker"]["reachable"] is False


def test_agent_timeout():
    def handler(request):
        raise httpx.ReadTimeout("lento")

    assert make_client(handler).get("/api/health").json()["status"] == "degraded"


def test_agent_returns_401():
    client = make_client(lambda request: httpx.Response(401))
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["agent"]["reachable"] is False


def test_agent_invalid_response():
    client = make_client(lambda request: httpx.Response(200, text="no es json"))
    assert client.get("/api/health").json()["agent"]["reachable"] is False


def test_docker_unreachable():
    def handler(request):
        return httpx.Response(
            200, json={"status": "ok", "docker": {"reachable": False, "server_version": None}}
        )

    body = make_client(handler).get("/api/health").json()
    assert body == {
        "status": "degraded",
        "agent": {"reachable": True},
        "docker": {"reachable": False},
    }


def test_security_headers():
    response = make_client(agent_ok).get("/api/health")
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_serves_panel():
    client = make_client(agent_ok)
    response = client.get("/")
    assert response.status_code == 200
    assert "MiniPaaS" in response.text
    assert response.headers["X-Frame-Options"] == "DENY"
    assert client.get("/js/app.js").status_code == 200


def test_agent_client_closed_on_shutdown():
    closed = []

    class SpyAgentClient(AgentClient):
        async def aclose(self) -> None:
            closed.append(True)
            await super().aclose()

    agent = SpyAgentClient("http://agent:8001", "t" * 40, transport=httpx.MockTransport(agent_ok))
    with TestClient(create_app(agent)):  # el bloque with ejecuta arranque y apagado
        pass
    assert closed == [True]
