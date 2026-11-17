"""Con Docker real: el agente detecta un contenedor creado fuera de la aplicación."""

import socket
import uuid

import docker
import pytest
from fastapi.testclient import TestClient

from server_monitor.agent.config import AgentSettings
from server_monitor.agent.main import create_app

pytestmark = pytest.mark.integration

IMAGE = "traefik/whoami:v1.11"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def agent():
    docker_client = docker.from_env()
    app = create_app(AgentSettings(), docker_client)
    return TestClient(app), docker_client


def test_detects_foreign_container_running_and_stopped(agent):
    client, docker_client = agent
    name = f"monitor-test-{uuid.uuid4().hex[:8]}"
    port = free_port()
    container = None
    try:
        container = docker_client.containers.run(
            IMAGE,
            name=name,
            detach=True,
            ports={"80/tcp": ("127.0.0.1", port)},
            labels={
                "com.docker.compose.project": "monitor-test-proyecto",
                "com.docker.compose.service": "monitor-test-servicio",
            },
        )

        found = {c["name"]: c for c in client.get("/containers").json()["containers"]}
        assert name in found
        item = found[name]
        assert item["image"] == IMAGE
        assert item["state"] == "running"
        assert item["id"] == container.id[:12]
        assert {
            "container_port": 80,
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
            "host_port": port,
        } in item["ports"]
        assert item["compose_project"] == "monitor-test-proyecto"
        assert item["compose_service"] == "monitor-test-servicio"

        container.stop(timeout=1)
        found = {c["name"]: c for c in client.get("/containers").json()["containers"]}
        assert found[name]["state"] == "exited"
    finally:
        if container is not None:
            container.remove(force=True)


def test_health_reports_real_docker(agent):
    client, _ = agent
    docker_status = client.get("/health").json()["docker"]
    assert docker_status["reachable"] is True
    assert docker_status["server_version"]


def test_real_host_metrics_are_coherent(agent):
    client, _ = agent
    body = client.get("/metrics").json()
    assert 0 <= body["cpu"]["percent"] <= 100
    assert body["cpu"]["cores"] > 0
    assert body["memory"]["total_bytes"] > 0
    assert 0 <= body["memory"]["percent"] <= 100
    assert body["memory"]["used_bytes"] <= body["memory"]["total_bytes"]
    assert body["disks"][0]["name"] == "Sistema"
    assert body["disks"][0]["total_bytes"] > 0
    assert 0 <= body["disks"][0]["percent"] <= 100
    assert body["uptime_seconds"] > 0
    assert body["os"]["kernel"]
    assert body["temperature"] is None or 0 < body["temperature"]["celsius"] <= 150
    assert body["network"] is None or body["network"]["rx_bytes"] >= 0
