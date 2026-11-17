from fakes import FakeDockerClient

from server_monitor.agent import containers

# IP de publicación de Docker (no es un servidor que escuche en 0.0.0.0).
ALL_IPS = "0.0.0.0"  # noqa: S104


def raw_container(name, state="running", status="Up 1 hour", ports=None, labels=None):
    return {
        "Id": name[0] * 64,
        "Names": [f"/{name}"],
        "Image": "img",
        "State": state,
        "Status": status,
        "Created": 1777600000,
        "Ports": ports or [],
        "Labels": labels,
    }


RAW = [
    raw_container("zeta", status="Up 3 hours (healthy)", labels={
        "com.docker.compose.project": "web",
        "com.docker.compose.service": "nginx",
    }, ports=[
        {"IP": ALL_IPS, "PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"},
        {"PrivatePort": 9000, "Type": "tcp"},
    ]),
    raw_container("alfa"),
]  # fmt: skip


def test_list_containers_converts_and_sorts():
    client = FakeDockerClient(RAW)
    result = containers.list_containers(client)

    # Una sola llamada de consulta, sin filtro: incluye los detenidos.
    assert client.api.calls == [("containers", {"all": True})]
    assert [c["name"] for c in result] == ["alfa", "zeta"]
    zeta = result[1]
    assert zeta["id"] == "z" * 12
    assert zeta["created_at"].endswith("Z")
    assert zeta["health"] == "healthy"
    assert zeta["ports"][0] == {
        "container_port": 80,
        "protocol": "tcp",
        "host_ip": ALL_IPS,
        "host_port": 8080,
    }
    assert zeta["ports"][1]["host_ip"] is None and zeta["ports"][1]["host_port"] is None
    assert (zeta["compose_project"], zeta["compose_service"]) == ("web", "nginx")
    assert result[0]["compose_project"] is None
    assert result[0]["health"] is None


def test_stopped_containers_included_and_running_first():
    raw = [
        raw_container("aaa", state="exited", status="Exited (0) 2 hours ago"),
        raw_container("zzz", state="running"),
        raw_container("bbb", state="paused", status="Up 1 hour (Paused)"),
        raw_container("mmm", state="running"),
    ]
    result = containers.list_containers(FakeDockerClient(raw))
    assert [(c["name"], c["state"]) for c in result] == [
        ("mmm", "running"),
        ("zzz", "running"),
        ("aaa", "exited"),
        ("bbb", "paused"),
    ]


def test_health_is_deduced_from_status_text():
    statuses = {
        "Up 3 hours (healthy)": "healthy",
        "Up 3 hours (unhealthy)": "unhealthy",
        "Up 5 seconds (health: starting)": "starting",
        "Up 3 hours": None,
        "Exited (0) 1 hour ago": None,
    }
    for status, expected in statuses.items():
        result = containers.list_containers(FakeDockerClient([raw_container("x", status=status)]))
        assert result[0]["health"] == expected, status


def test_docker_status():
    assert containers.docker_status(FakeDockerClient()) == {
        "reachable": True,
        "server_version": "27.0.1",
    }
    down = containers.docker_status(FakeDockerClient(error=OSError("caído")))
    assert down == {"reachable": False, "server_version": None}
