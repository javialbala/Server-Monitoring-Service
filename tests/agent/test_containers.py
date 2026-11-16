from fakes import FakeDockerClient

from minipaas.agent import containers

# IP de publicación de Docker (no es un servidor que escuche en 0.0.0.0).
ALL_IPS = "0.0.0.0"  # noqa: S104

RAW = [
    {
        "Id": "b" * 64,
        "Names": ["/zeta"],
        "Image": "nginx:1",
        "State": "running",
        "Status": "Up 3 hours",
        "Created": 1777600000,
        "Ports": [
            {"IP": ALL_IPS, "PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"},
            {"PrivatePort": 9000, "Type": "tcp"},
        ],
        "Labels": {
            "com.docker.compose.project": "web",
            "com.docker.compose.service": "nginx",
        },
    },
    {
        "Id": "a" * 64,
        "Names": ["/alfa"],
        "Image": "redis",
        "State": "running",
        "Status": "Up 1 minute",
        "Created": 1777600000,
        "Ports": [],
        "Labels": None,
    },
]


def test_list_running_containers_converts_and_sorts():
    client = FakeDockerClient(RAW)
    result = containers.list_running_containers(client)

    assert client.api.calls == [("containers", {"filters": {"status": "running"}})]
    assert [c["name"] for c in result] == ["alfa", "zeta"]
    zeta = result[1]
    assert zeta["id"] == "b" * 12
    assert zeta["created_at"].endswith("Z")
    assert zeta["ports"][0] == {
        "container_port": 80,
        "protocol": "tcp",
        "host_ip": ALL_IPS,
        "host_port": 8080,
    }
    assert zeta["ports"][1]["host_ip"] is None and zeta["ports"][1]["host_port"] is None
    assert (zeta["compose_project"], zeta["compose_service"]) == ("web", "nginx")
    assert result[0]["compose_project"] is None


def test_docker_status():
    assert containers.docker_status(FakeDockerClient()) == {
        "reachable": True,
        "server_version": "27.0.1",
    }
    down = containers.docker_status(FakeDockerClient(error=OSError("caído")))
    assert down == {"reachable": False, "server_version": None}
