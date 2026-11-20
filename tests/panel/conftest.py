import httpx
import pytest
from fastapi.testclient import TestClient

from server_monitor.panel.agent_client import AgentClient
from server_monitor.panel.config import PanelSettings
from server_monitor.panel.main import create_app
from server_monitor.panel.security.passwords import hash_password

PASSWORD = "clave-de-prueba"
METRICS = {"hostname": "servidor", "cpu": {"percent": 12.5, "cores": 4, "model": None}}
CONTAINERS = {"collected_at": "2030-01-01T00:00:00Z", "containers": [{"name": "jellyfin"}]}
IMAGES = {"collected_at": "2030-01-01T00:00:00Z", "images": [{"repository": "nginx"}]}
DOCKER = {"reachable": True, "server_version": "27.0.1"}
RESPONSES = {
    "/metrics": METRICS,
    "/containers": CONTAINERS,
    "/images": IMAGES,
    "/health": {"status": "ok", "docker": DOCKER},
}


class FakeAgent:
    """Responde como el agente; `down = True` simula que se ha caído."""

    def __init__(self) -> None:
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(500)
        return httpx.Response(200, json=RESPONSES[request.url.path])


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def client(agent):
    agent_client = AgentClient("http://agent:8001", transport=httpx.MockTransport(agent))
    app = create_app(PanelSettings(), agent_client, hash_password(PASSWORD))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def csrf(client) -> str:
    """Inicia sesión y devuelve el token CSRF (la cookie queda en `client`)."""
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return client.get("/api/session").json()["csrf_token"]
