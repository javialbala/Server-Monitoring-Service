"""Comportamiento de DockerRuntime.ping() ante fallos, sin Docker real."""

from docker.errors import DockerException
from requests.exceptions import ConnectionError as RequestsConnectionError

from minipaas.agent.docker_runtime import DockerRuntime


class FailingClient:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def version(self):
        raise self._error


def runtime_with(client) -> DockerRuntime:
    runtime = DockerRuntime()
    runtime._client = client  # se inyecta un cliente falso en lugar del SDK real
    return runtime


def test_ping_ok():
    class OkClient:
        def version(self):
            return {"Version": "29.0.0"}

    status = runtime_with(OkClient()).ping()
    assert status.reachable is True
    assert status.server_version == "29.0.0"


def test_ping_docker_exception():
    status = runtime_with(FailingClient(DockerException("sin socket"))).ping()
    assert status.reachable is False
    assert status.server_version is None


def test_ping_docker_stops_after_client_created():
    # El SDK lanza errores de requests (no DockerException) si Docker deja de responder.
    status = runtime_with(FailingClient(RequestsConnectionError("conexión rechazada"))).ping()
    assert status.reachable is False
