import pytest
from fakes import TOKEN
from fastapi.testclient import TestClient

from minipaas.agent.config import AgentSettings
from minipaas.agent.main import create_app


@pytest.fixture
def make_client(tmp_path):
    def make(docker_client) -> TestClient:
        token_file = tmp_path / "token"
        token_file.write_text(TOKEN)
        settings = AgentSettings(token_file=str(token_file), hostfs=str(tmp_path))
        return TestClient(create_app(settings, docker_client))

    return make
