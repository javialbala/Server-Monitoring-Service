import pytest
from fastapi.testclient import TestClient

from minipaas.agent.config import AgentSettings
from minipaas.agent.docker_runtime import DockerStatus
from minipaas.agent.main import create_app

TOKEN = "t" * 40


class FakeRuntime:
    def __init__(self, status: DockerStatus):
        self._status = status

    def ping(self) -> DockerStatus:
        return self._status


def make_client(tmp_path, status: DockerStatus) -> TestClient:
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN + "\n")
    app = create_app(AgentSettings(token_file=str(token_file)), FakeRuntime(status))
    return TestClient(app)


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path, DockerStatus(reachable=True, server_version="29.0.0"))


def test_requires_token(client):
    assert client.get("/health").status_code == 401


def test_rejects_wrong_token(client):
    response = client.get("/health", headers={"Authorization": "Bearer incorrecto"})
    assert response.status_code == 401


def test_health_ok(client):
    response = client.get("/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "docker": {"reachable": True, "server_version": "29.0.0"},
    }


def test_health_docker_unreachable(tmp_path):
    client = make_client(tmp_path, DockerStatus(reachable=False, server_version=None))
    response = client.get("/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["docker"] == {"reachable": False, "server_version": None}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_openapi_docs(client, path):
    assert client.get(path).status_code == 404
