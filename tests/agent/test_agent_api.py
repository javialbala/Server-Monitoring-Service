from fakes import FakeDockerClient
from fastapi.routing import APIRoute

from server_monitor.agent import host_metrics


def test_only_get_routes(make_client):
    client = make_client(FakeDockerClient())
    routes = [r for r in client.app.routes if isinstance(r, APIRoute)]
    assert {r.path for r in routes} == {"/health", "/metrics", "/containers"}
    for route in routes:
        assert route.methods == {"GET"}


def test_no_docs_and_no_write_methods(make_client):
    client = make_client(FakeDockerClient())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    assert client.post("/containers").status_code == 405


def test_health(make_client):
    response = make_client(FakeDockerClient()).get("/health")
    assert response.json() == {
        "status": "ok",
        "docker": {"reachable": True, "server_version": "27.0.1"},
    }


def test_health_with_docker_down(make_client):
    client = make_client(FakeDockerClient(error=OSError("caído")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["docker"] == {"reachable": False, "server_version": None}


def test_containers_only_queries_docker(make_client):
    raw = [
        {
            "Id": "c" * 64,
            "Names": ["/web"],
            "Image": "nginx",
            "State": "running",
            "Status": "Up",
            "Created": 1777600000,
            "Ports": [],
            "Labels": {},
        }
    ]
    docker_client = FakeDockerClient(raw)
    response = make_client(docker_client).get("/containers")
    assert response.status_code == 200
    assert response.json()["containers"][0]["name"] == "web"
    assert docker_client.api.calls == [("containers", {"all": True})]


def test_containers_docker_down_returns_503_without_details(make_client):
    client = make_client(FakeDockerClient(error=OSError("/var/run/docker.sock secreto")))
    response = client.get("/containers")
    assert response.status_code == 503
    assert response.json() == {"detail": "Docker no está disponible"}


def test_metrics_with_fake_host(make_client, tmp_path, monkeypatch):
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc/hostname").write_text("servidor\n")
    (tmp_path / "net_dev").write_text(
        "cabecera 1\ncabecera 2\neth0: 100 1 0 0 0 0 0 0 50 1 0 0 0 0 0 0\n"
    )
    monkeypatch.setattr(host_metrics, "read_cpu_percent", lambda _proc: 12.5)
    response = make_client(FakeDockerClient()).get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["hostname"] == "servidor"
    assert body["cpu"]["percent"] == 12.5
    assert set(body) == {
        "collected_at", "hostname", "os", "uptime_seconds", "cpu",
        "memory", "disks", "temperature", "network",
    }  # fmt: skip
    assert [d["name"] for d in body["disks"]] == ["Sistema"] and "disk" not in body
    assert body["network"]["rx_bytes"] == 100 and body["network"]["tx_bytes"] == 50
    assert body["temperature"] is None or body["temperature"]["celsius"] > 0
    assert body["collected_at"].endswith("Z") and "." in body["collected_at"]
