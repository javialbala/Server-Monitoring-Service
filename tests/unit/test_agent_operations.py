"""AgentOperations directamente, con el doble de Docker: registros y errores."""

import logging

import docker.errors
import pytest
from agent_fakes import FakeRuntime

from minipaas.agent.config import AgentSettings
from minipaas.agent.errors import AgentError, summarize_docker_error
from minipaas.agent.operations import AgentOperations
from minipaas.common.agent_protocol import CreateContainerRequest

OP = "6f1f4b6e-8c0e-4a7e-9d3a-2b1c0d9e8f7a"


def make_ops(instance="dev") -> tuple[AgentOperations, FakeRuntime]:
    runtime = FakeRuntime()
    return AgentOperations(AgentSettings(token_file="x", instance=instance), runtime), runtime


def request(env=None) -> CreateContainerRequest:
    return CreateContainerRequest.model_validate(
        {
            "operation_id": OP,
            "app_id": 1,
            "app_slug": "mi-app",
            "revision": 1,
            "service": {
                "service_name": "web",
                "catalog_id": "whoami",
                "internal_port": 80,
                "env": env or {},
                "memory_mb": 32,
                "cpus": 0.25,
            },
        }
    )


def test_env_values_never_logged(caplog):
    ops, _ = make_ops()
    ops.ensure_networks("mi-app", 1)
    with caplog.at_level(logging.DEBUG):
        ops.create_container("mi-app", request({"WHOAMI_NAME": "valor-secreto"}))
    assert "valor-secreto" not in caplog.text


def test_instances_do_not_see_each_other():
    ops_dev, runtime = make_ops("dev")
    ops_dev.ensure_networks("mi-app", 1)
    ops_dev.create_container("mi-app", request())
    other = AgentOperations(AgentSettings(token_file="x", instance="e2e"), runtime)
    assert other.list_containers("mi-app") == []
    assert other.cleanup_operation("mi-app", OP) == []
    assert other.delete_app("mi-app") == []
    assert len(runtime.fake.container_objs) == 1


def test_invalid_slug_raises_400():
    ops, _ = make_ops()
    with pytest.raises(AgentError) as info:
        ops.list_containers("../etc")
    assert info.value.status == 400


def test_summary_is_short_and_without_paths():
    error = docker.errors.APIError("x", explanation="fallo\nsegunda línea en /var/lib/docker/z")
    assert summarize_docker_error(error) == "fallo"
    error = docker.errors.APIError("x", explanation="a " * 300 + "/var/run/docker.sock")
    assert len(summarize_docker_error(error)) == 200
    assert "/var/run" not in summarize_docker_error(
        docker.errors.APIError("x", explanation="/var/run/docker.sock")
    )
