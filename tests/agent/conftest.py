import pytest
from fastapi.testclient import TestClient

from server_monitor.agent.config import AgentSettings
from server_monitor.agent.main import create_app


@pytest.fixture
def make_client(tmp_path):
    def make(docker_client) -> TestClient:
        settings = AgentSettings(
            hostfs=str(tmp_path),
            disks_dir=str(tmp_path / "disks"),
            net_dev=str(tmp_path / "net_dev"),
        )
        return TestClient(create_app(settings, docker_client))

    return make
