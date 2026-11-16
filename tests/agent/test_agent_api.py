from fakes import AUTH, FakeDockerClient
from fastapi.routing import APIRoute

from minipaas.agent import host_metrics


def test_all_routes_are_get_and_require_token(make_client):
    client = make_client(FakeDockerClient())
    routes = [r for r in client.app.routes if isinstance(r, APIRoute)]
    assert {r.path for r in routes} == {"/health", "/metrics", "/containers"}
    for route in routes:
        assert route.methods == {"GET"}
        assert client.get(route.path).status_code == 401
        assert client.get(route.path, headers={"Authorization": "Bearer mal"}).status_code == 401


def test_no_docs_and_no_write_methods(make_client):
    client = make_client(FakeDockerClient())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=AUTH).status_code == 404
    assert client.post("/containers", headers=AUTH).status_code == 405


def test_health(make_client):
    response = make_client(FakeDockerClient()).get("/health", headers=AUTH)
    assert response.json() == {
        "status": "ok",
        "docker": {"reachable": True, "server_version": "27.0.1"},
    }


def test_health_with_docker_down(make_client):
    client = make_client(FakeDockerClient(error=OSError("caído")))
    response = client.get("/health", headers=AUTH)
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
    response = make_client(docker_client).get("/containers", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["containers"][0]["name"] == "web"
    # La única llamada permitida es la consulta; el fake falla ante cualquier otra.
    assert docker_client.api.calls == [("containers", {"filters": {"status": "running"}})]


def test_containers_docker_down_returns_503_without_details(make_client):
    client = make_client(FakeDockerClient(error=OSError("/var/run/docker.sock secreto")))
    response = client.get("/containers", headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"detail": "Docker no está disponible"}


def test_metrics_with_fake_host(make_client, tmp_path, monkeypatch):
    # El agente lee la raíz del anfitrión (hostfs) de los ajustes; /proc se simula.
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc/hostname").write_text("servidor\n")
    monkeypatch.setattr(host_metrics, "read_cpu_percent", lambda _proc: 12.5)
    response = make_client(FakeDockerClient()).get("/metrics", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["hostname"] == "servidor"
    assert body["cpu"]["percent"] == 12.5
    assert set(body) == {
        "collected_at", "hostname", "os", "uptime_seconds", "cpu",
        "memory", "disk", "temperatures",
    }  # fmt: skip
