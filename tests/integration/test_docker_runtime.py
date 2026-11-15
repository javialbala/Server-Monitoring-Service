import pytest

from minipaas.agent.docker_runtime import DockerRuntime

pytestmark = pytest.mark.integration  # requiere Docker local


def test_ping_real_docker():
    status = DockerRuntime().ping()
    assert status.reachable is True
    assert status.server_version
