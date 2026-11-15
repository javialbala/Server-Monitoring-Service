import httpx
import pytest

from minipaas.common.agent_protocol import TIMEOUTS
from minipaas.controlplane.agent_runtime_client import (
    AgentDockerError,
    AgentRejected,
    AgentRuntimeClient,
    AgentUnavailable,
)

TOKEN = "token-secreto-" + "x" * 30


def client_for(handler) -> AgentRuntimeClient:
    return AgentRuntimeClient("http://agent:8001", TOKEN, httpx.MockTransport(handler))


def test_sends_token_and_parses_response():
    def handler(request):
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        return httpx.Response(200, json={"containers": []})

    assert client_for(handler).list_containers("demo") == []


@pytest.mark.parametrize("error", [httpx.ConnectError("x"), httpx.ReadTimeout("x")])
def test_network_errors_are_unavailable(error):
    def handler(request):
        raise error

    with pytest.raises(AgentUnavailable) as caught:
        client_for(handler).catalog()
    assert TOKEN not in str(caught.value)


def test_503_is_unavailable():
    body = {"detail": "Docker no responde", "code": "docker_unavailable"}
    with pytest.raises(AgentUnavailable):
        client_for(lambda r: httpx.Response(503, json=body)).catalog()


def test_4xx_is_rejected_with_code():
    body = {"detail": "Ya existe", "code": "conflict"}
    with pytest.raises(AgentRejected) as caught:
        client_for(lambda r: httpx.Response(409, json=body)).delete_networks("demo")
    assert (caught.value.status, caught.value.code, caught.value.detail) == (
        409,
        "conflict",
        "Ya existe",
    )


def test_502_and_garbage_are_docker_errors():
    body = {"detail": "falló", "code": "docker_error"}
    with pytest.raises(AgentDockerError):
        client_for(lambda r: httpx.Response(502, json=body)).catalog()
    with pytest.raises(AgentDockerError):
        client_for(lambda r: httpx.Response(200, json={"otra": "cosa"})).catalog()
    with pytest.raises(AgentRejected):  # cuerpo de error ilegible
        client_for(lambda r: httpx.Response(404, text="no")).probe("demo", "c")


def test_each_operation_uses_its_own_timeout():
    seen = {}

    def handler(request):
        seen[request.url.path] = request.extensions["timeout"]["read"]
        return httpx.Response(200, json={"removed": []})

    client = client_for(handler)
    client.cleanup_operation("demo", "op")
    assert seen["/apps/demo/operations/op/cleanup"] == TIMEOUTS["remove"]
