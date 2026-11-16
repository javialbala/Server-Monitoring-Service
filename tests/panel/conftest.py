"""Fixtures del panel: app con un agente falso (httpx.MockTransport) y contraseña de prueba."""

import httpx
import pytest
from fastapi.testclient import TestClient

from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.config import ControlPlaneSettings
from minipaas.controlplane.main import create_app
from minipaas.controlplane.manage import write_hash_file
from minipaas.controlplane.security.passwords import hash_password

PASSWORD = "clave-de-prueba"
METRICS = {"hostname": "servidor", "cpu": {"percent": 12.5, "cores": 4, "model": None}}
CONTAINERS = {"collected_at": "2030-01-01T00:00:00Z", "containers": [{"name": "jellyfin"}]}


class FakeAgent:
    """Responde como el agente; `down = True` simula que se ha caído."""

    def __init__(self) -> None:
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(500)
        assert request.headers["Authorization"] == "Bearer " + "t" * 40
        return httpx.Response(
            200, json={"/metrics": METRICS, "/containers": CONTAINERS}[request.url.path]
        )


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def hash_file(tmp_path):
    path = tmp_path / "password_hash"
    write_hash_file(str(path), hash_password(PASSWORD))
    return path


@pytest.fixture
def settings(hash_file) -> ControlPlaneSettings:
    return ControlPlaneSettings(
        agent_url="http://agent:8001", token_file="/no/se/usa", password_hash_file=str(hash_file)
    )


@pytest.fixture
def client(settings, agent):
    agent_client = AgentClient("http://agent:8001", "t" * 40, transport=httpx.MockTransport(agent))
    with TestClient(create_app(settings, agent_client)) as test_client:
        yield test_client


@pytest.fixture
def csrf(client) -> str:
    """Inicia sesión y devuelve el token CSRF (la cookie queda en `client`)."""
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return client.get("/api/session").json()["csrf_token"]
