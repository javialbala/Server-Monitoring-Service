"""API del agente con un doble de Docker (sin Docker real)."""

import copy
import uuid

import docker.errors
import pytest
from agent_fakes import FakeContainer, FakeRuntime
from fastapi.testclient import TestClient
from requests.exceptions import ConnectionError as RequestsConnectionError

from minipaas.agent.config import AgentSettings
from minipaas.agent.docker_runtime import DockerStatus
from minipaas.agent.main import create_app
from minipaas.common.catalog import NGINX_STATIC
from minipaas.common.naming import container_name, edge_network_name, internal_network_name

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}
SLUG = "mi-app"
OP = "6f1f4b6e-8c0e-4a7e-9d3a-2b1c0d9e8f7a"
OP2 = "7f1f4b6e-8c0e-4a7e-9d3a-2b1c0d9e8f7b"


def make_client(tmp_path, runtime=None, **settings) -> TestClient:
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN + "\n")
    config = AgentSettings(token_file=str(token_file), **settings)
    return TestClient(create_app(config, runtime or FakeRuntime()))


@pytest.fixture
def runtime():
    return FakeRuntime()


@pytest.fixture
def client(tmp_path, runtime):
    return make_client(tmp_path, runtime)


def body(operation=OP, slug=SLUG, **service):
    spec = {
        "service_name": "web",
        "catalog_id": "whoami",
        "internal_port": 80,
        "host_port": 20900,
        "env": {},
        "memory_mb": 32,
        "cpus": 0.25,
    }
    spec.update(service)
    return {
        "operation_id": operation,
        "app_id": 7,
        "app_slug": slug,
        "revision": 1,
        "service": spec,
    }


def prepare(client, slug=SLUG):
    r = client.post(f"/apps/{slug}/networks", json={"app_id": 7}, headers=AUTH)
    assert r.status_code == 200, r.text


def create(client, payload=None, slug=SLUG):
    return client.post(f"/apps/{slug}/containers", json=payload or body(), headers=AUTH)


def name_of(service="web", slug=SLUG, instance="dev"):
    return container_name(instance, slug, service, 1)


# --- autenticación y rutas -------------------------------------------------------------

ROUTES = [
    ("GET", "/health"),
    ("GET", "/catalog"),
    ("POST", "/images/ensure"),
    ("POST", f"/apps/{SLUG}/networks"),
    ("DELETE", f"/apps/{SLUG}/networks"),
    ("GET", f"/apps/{SLUG}/containers"),
    ("POST", f"/apps/{SLUG}/containers"),
    ("POST", f"/apps/{SLUG}/containers/x/start"),
    ("POST", f"/apps/{SLUG}/containers/x/stop"),
    ("DELETE", f"/apps/{SLUG}/containers/x"),
    ("POST", f"/apps/{SLUG}/containers/x/probe"),
    ("POST", f"/apps/{SLUG}/operations/{OP}/cleanup"),
    ("DELETE", f"/apps/{SLUG}"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_route_requires_token(client, method, path):
    assert client.request(method, path).status_code == 401
    wrong = client.request(method, path, headers={"Authorization": "Bearer incorrecto"})
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "unauthorized"


def test_health_ok(client):
    response = client.get("/health", headers=AUTH)
    assert response.json() == {
        "status": "ok",
        "docker": {"reachable": True, "server_version": "29.0.0"},
    }


def test_health_docker_unreachable(tmp_path):
    runtime = FakeRuntime(DockerStatus(reachable=False, server_version=None))
    response = make_client(tmp_path, runtime).get("/health", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["docker"] == {"reachable": False, "server_version": None}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/exec", "/containers/json"])
def test_unknown_routes_are_404(client, path):
    response = client.get(path, headers=AUTH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_unknown_method_is_405(client):
    assert client.put(f"/apps/{SLUG}/containers", headers=AUTH).status_code == 405


def test_catalog_hides_test_entries_by_default(client):
    data = client.get("/catalog", headers=AUTH).json()
    assert data["architecture"] == "amd64"
    assert data["instance"] == "dev"
    assert data["publish_address"] == "127.0.0.1"
    assert {e["id"] for e in data["entries"]} == {"nginx-static", "whoami"}


def test_catalog_with_test_entries(tmp_path):
    client = make_client(tmp_path, enable_test_catalog=True)
    ids = {e["id"] for e in client.get("/catalog", headers=AUTH).json()["entries"]}
    assert {"test-crash", "test-unhealthy"} <= ids


# --- imágenes --------------------------------------------------------------------------


def test_ensure_image_already_present(client, runtime):
    r = client.post("/images/ensure", json={"catalog_id": "whoami"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["pulled"] is False
    assert runtime.fake.pulled == []


def test_ensure_image_pulls_by_digest(client, runtime):
    runtime.fake.image_objs.clear()
    r = client.post("/images/ensure", json={"catalog_id": "nginx-static"}, headers=AUTH)
    assert r.json()["pulled"] is True
    assert all("@sha256:" in ref for ref in runtime.fake.pulled)


def test_ensure_image_unknown_catalog(client):
    r = client.post("/images/ensure", json={"catalog_id": "otra-cosa"}, headers=AUTH)
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_request"


# --- creación y validación -------------------------------------------------------------


def test_create_ok_then_idempotent(client, runtime):
    prepare(client)
    first = create(client)
    assert first.status_code == 201
    again = create(client)
    assert again.status_code == 200
    assert again.json() == first.json()
    assert len(runtime.fake.created) == 1


def test_create_other_operation_same_name_conflicts(client):
    prepare(client)
    create(client)
    r = create(client, body(operation=OP2))
    assert r.status_code == 409
    assert r.json()["code"] == "conflict"


def test_create_requires_networks(client):
    r = create(client)
    assert r.status_code == 409
    assert "red" in r.json()["detail"]


def test_create_without_host_port_needs_no_edge(client, runtime):
    prepare(client)
    runtime.fake.network_objs.pop(edge_network_name("dev", SLUG))
    assert create(client, body(host_port=None)).status_code == 201


def test_create_slug_mismatch(client):
    prepare(client)
    assert create(client, body(slug="otra-app")).status_code == 400


def test_create_invalid_slug(client):
    r = create(client, body(slug="Mal_Slug"), slug="Mal_Slug")
    assert r.status_code in (400, 422)


def test_create_unknown_catalog(client):
    prepare(client)
    assert create(client, body(catalog_id="ubuntu")).status_code == 400


def test_test_entry_needs_flag(client, tmp_path):
    prepare(client)
    payload = body(catalog_id="test-crash", internal_port=8080, memory_mb=64, cpus=0.25)
    assert create(client, payload).status_code == 400
    enabled = make_client(tmp_path, enable_test_catalog=True)
    prepare(enabled)
    assert create(enabled, payload).status_code == 201


def test_incompatible_architecture(client, runtime):
    prepare(client)
    runtime.fake.architecture = "mips64"
    r = create(client)
    assert r.status_code == 400
    assert "arquitectura" in r.json()["detail"]


def test_digest_mismatch(client, runtime):
    prepare(client)
    runtime.fake.image_objs[NGINX_STATIC.image_ref] = [
        "nginxinc/nginx-unprivileged@sha256:" + "0" * 64
    ]
    payload = body(catalog_id="nginx-static", internal_port=8080, memory_mb=64, cpus=0.5)
    r = create(client, payload)
    assert r.status_code == 409
    assert "digest" in r.json()["detail"]


def test_image_missing(client, runtime):
    prepare(client)
    runtime.fake.image_objs.clear()
    assert create(client).status_code == 409


@pytest.mark.parametrize(
    ("override", "status"),
    [
        ({"internal_port": 22}, 400),
        ({"host_port": 80}, 422),
        ({"host_port": 21000}, 422),
        ({"env": {"PATH": "x"}}, 400),
        ({"env": {"WHOAMI_NAME": "a;rm -rf /"}}, 400),
        ({"memory_mb": 512}, 400),
        ({"cpus": 4}, 400),
        ({"privileged": True}, 422),
        ({"command": ["sh"]}, 422),
        ({"image": "alpine"}, 422),
        ({"service_name": "Web_1"}, 422),
    ],
)
def test_create_rejects_invalid_service(client, override, status):
    prepare(client)
    assert create(client, body(**override)).status_code == status


@pytest.mark.parametrize("extra", ["privileged", "command", "image", "volumes", "network_mode"])
def test_create_rejects_extra_top_level_fields(client, extra):
    prepare(client)
    payload = body()
    payload[extra] = True
    assert create(client, payload).status_code == 422


def test_validation_error_does_not_echo_values(client):
    prepare(client)
    r = create(client, body(env={"X": "valor-secreto-123"}, privileged=True))
    assert r.status_code == 422
    assert "valor-secreto-123" not in r.text


def test_built_container_is_hardened(client, runtime):
    prepare(client)
    secret = "secreto-xyz"
    assert create(client, body(env={"WHOAMI_NAME": secret})).status_code == 201
    kwargs = runtime.fake.created[0].create_kwargs
    assert kwargs["image" if "image" in kwargs else "name"]
    assert (
        runtime.fake.created[0].image
        == "traefik/whoami@" + runtime.fake.created[0].image.split("@")[1]
    )
    assert kwargs["read_only"] is True
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["security_opt"] == ["no-new-privileges:true"]
    assert kwargs["privileged"] is False
    assert kwargs["mem_limit"] == kwargs["memswap_limit"] == "32m"
    assert kwargs["nano_cpus"] == 250_000_000
    assert kwargs["pids_limit"] == 32
    assert kwargs["user"] == "65534:65534"
    assert kwargs["restart_policy"] == {"Name": "no"}
    assert kwargs["environment"] == {"WHOAMI_NAME": secret}
    assert kwargs["hostname"] == "web"
    for forbidden in ("volumes", "devices", "binds", "cap_add", "network_mode", "command"):
        assert forbidden not in kwargs
    assert kwargs["networking_config"] == {internal_network_name("dev", SLUG): {"Aliases": ["web"]}}
    labels = kwargs["labels"]
    assert labels["minipaas.managed"] == "true"
    assert labels["minipaas.instance"] == "dev"
    assert labels["minipaas.app"] == SLUG
    assert labels["minipaas.role"] == "service"
    assert labels["minipaas.operation"] == OP
    assert labels["minipaas.catalog"] == "whoami"
    assert labels["minipaas.internal_port"] == "80"
    assert labels["minipaas.app_id"] == "7"
    assert labels["minipaas.service"] == "web"
    assert labels["minipaas.revision"] == "1"


def test_published_port_uses_agent_address_and_edge_network(tmp_path, runtime):
    client = make_client(tmp_path, runtime, publish_address="192.168.1.5")
    prepare(client)
    r = create(client)
    assert r.json()["host_port"] == 20900
    assert r.json()["publish_address"] == "192.168.1.5"
    created = runtime.fake.created[0]
    assert created.create_kwargs["ports"] == {"80/tcp": ("192.168.1.5", 20900)}
    assert created.networks == [internal_network_name("dev", SLUG), edge_network_name("dev", SLUG)]


def test_unpublished_service_only_in_internal_network(client, runtime):
    prepare(client)
    create(client, body(host_port=None))
    created = runtime.fake.created[0]
    assert created.create_kwargs["ports"] is None
    assert created.networks == [internal_network_name("dev", SLUG)]


def test_request_cannot_set_publish_address(client):
    prepare(client)
    payload = body()
    payload["service"]["publish_address"] = "0.0.0.0"  # noqa: S104
    assert create(client, payload).status_code == 422


# --- redes ----------------------------------------------------------------------------


def test_networks_are_created_with_expected_options(client, runtime):
    prepare(client)
    internal = runtime.fake.network_objs[internal_network_name("dev", SLUG)]
    edge = runtime.fake.network_objs[edge_network_name("dev", SLUG)]
    assert internal.attrs["Internal"] is True
    assert edge.attrs["Internal"] is False
    assert edge.options == {"com.docker.network.bridge.enable_ip_masquerade": "false"}
    assert internal.attrs["Labels"]["minipaas.role"] == "network-internal"
    assert edge.attrs["Labels"]["minipaas.role"] == "network-edge"
    prepare(client)  # idempotente
    assert len(runtime.fake.network_objs) == 2


def test_foreign_network_with_same_name_conflicts(client, runtime):
    runtime.fake.networks.create(internal_network_name("dev", SLUG), labels={})
    r = client.post(f"/apps/{SLUG}/networks", json={"app_id": 7}, headers=AUTH)
    assert r.status_code == 409


def test_delete_networks_refuses_with_containers(client):
    prepare(client)
    create(client)
    assert client.delete(f"/apps/{SLUG}/networks", headers=AUTH).status_code == 409


def test_delete_networks_ok(client, runtime):
    prepare(client)
    r = client.delete(f"/apps/{SLUG}/networks", headers=AUTH)
    assert r.status_code == 200
    assert len(r.json()["networks"]) == 2
    assert runtime.fake.network_objs == {}


# --- start / stop / remove / listado ---------------------------------------------------


def test_start_stop_cycle_and_noops(client):
    prepare(client)
    create(client)
    url = f"/apps/{SLUG}/containers/{name_of()}"
    assert client.post(f"{url}/stop", headers=AUTH).json()["state"] == "created"
    assert client.post(f"{url}/start", headers=AUTH).json()["state"] == "running"
    assert client.post(f"{url}/start", headers=AUTH).status_code == 200  # no-op
    assert client.post(f"{url}/stop", headers=AUTH).json()["state"] == "exited"
    assert client.post(f"{url}/stop", headers=AUTH).status_code == 200  # no-op
    listed = client.get(f"/apps/{SLUG}/containers", headers=AUTH).json()["containers"]
    assert [c["name"] for c in listed] == [name_of()]


def test_start_docker_error_is_summarized(client, runtime):
    prepare(client)
    create(client)
    error = docker.errors.APIError("x", explanation="port is already allocated " + "y" * 400)
    runtime.fake.created[0].start_error = error
    r = client.post(f"/apps/{SLUG}/containers/{name_of()}/start", headers=AUTH)
    assert r.status_code == 502
    assert r.json()["code"] == "docker_error"
    assert len(r.json()["detail"]) <= 200


def test_remove_container(client, runtime):
    prepare(client)
    create(client)
    r = client.delete(f"/apps/{SLUG}/containers/{name_of()}", headers=AUTH)
    assert r.status_code == 204
    assert runtime.fake.container_objs == {}


def add_foreign(runtime, name, labels):
    c = FakeContainer(runtime.fake, name, labels, {})
    c.status = "running"
    runtime.fake.container_objs[name] = c
    return c


def owned_labels(**changes):
    labels = {
        "minipaas.managed": "true",
        "minipaas.instance": "dev",
        "minipaas.app": SLUG,
        "minipaas.role": "service",
    }
    labels.update(changes)
    return labels


@pytest.mark.parametrize(
    "labels",
    [
        {},
        {"minipaas.instance": "dev", "minipaas.app": SLUG, "minipaas.role": "service"},
        owned_labels(**{"minipaas.app": "otra-app"}),
        owned_labels(**{"minipaas.instance": "e2e"}),
        owned_labels(**{"minipaas.role": "probe"}),
        owned_labels(**{"minipaas.managed": "false"}),
    ],
)
@pytest.mark.parametrize("action", ["start", "stop", "probe", "remove"])
def test_foreign_resources_are_404(client, runtime, labels, action):
    name = name_of(service="ajeno")
    add_foreign(runtime, name, labels)
    url = f"/apps/{SLUG}/containers/{name}"
    if action == "remove":
        response = client.delete(url, headers=AUTH)
    else:
        response = client.post(f"{url}/{action}", headers=AUTH)
    assert response.status_code == 404
    assert name in runtime.fake.container_objs
    assert runtime.fake.container_objs[name].status == "running"
    missing = client.post(f"/apps/{SLUG}/containers/{name_of('no-existe')}/start", headers=AUTH)
    assert missing.json() == response.json()  # mismo mensaje: no revela si existe


def test_name_outside_app_prefix_is_404(client, runtime):
    add_foreign(runtime, "calendar_paas_db", owned_labels())
    r = client.post(f"/apps/{SLUG}/containers/calendar_paas_db/stop", headers=AUTH)
    assert r.status_code == 404


def test_invalid_slug_is_rejected(client):
    assert client.delete("/apps/Mal_Slug", headers=AUTH).status_code == 400
    assert client.get("/apps/Mal_Slug/containers", headers=AUTH).status_code == 400


def test_list_ignores_other_apps_and_instances(client, runtime):
    prepare(client)
    create(client)
    add_foreign(runtime, "otro-1", owned_labels(**{"minipaas.app": "otra-app"}))
    add_foreign(runtime, "otro-2", owned_labels(**{"minipaas.instance": "e2e"}))
    listed = client.get(f"/apps/{SLUG}/containers", headers=AUTH).json()["containers"]
    assert len(listed) == 1


# --- sonda ------------------------------------------------------------------------------


def test_probe_not_running(client):
    prepare(client)
    create(client)
    r = client.post(f"/apps/{SLUG}/containers/{name_of()}/probe", headers=AUTH)
    assert r.json() == {"healthy": False, "detail": "El servicio no está en ejecución"}


@pytest.mark.parametrize(("exit_code", "healthy"), [(0, True), (1, False)])
def test_probe_runs_and_removes_ephemeral_container(client, runtime, exit_code, healthy):
    prepare(client)
    create(client)
    client.post(f"/apps/{SLUG}/containers/{name_of()}/start", headers=AUTH)
    original = runtime.fake.containers.create

    def create_probe(image, **kwargs):
        probe = original(image, **kwargs)
        probe.wait_exit_code = exit_code
        return probe

    runtime.fake.containers.create = create_probe
    r = client.post(f"/apps/{SLUG}/containers/{name_of()}/probe", headers=AUTH)
    assert r.json()["healthy"] is healthy
    probe = runtime.fake.created[-1]
    assert probe.removed is True
    kwargs = probe.create_kwargs
    assert kwargs["entrypoint"] == ["wget"]
    assert kwargs["command"][-1] == "http://web:80/health"
    assert kwargs["read_only"] is True
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["labels"]["minipaas.role"] == "probe"
    assert kwargs["labels"]["minipaas.operation"] == OP
    assert kwargs["network"] == internal_network_name("dev", SLUG)


# --- limpieza ---------------------------------------------------------------------------


def test_cleanup_only_removes_that_operation(client, runtime):
    prepare(client)
    create(client)
    create(client, body(operation=OP2, service_name="db", host_port=None))
    other_app = add_foreign(runtime, "otra", owned_labels(**{"minipaas.app": "otra-app"}))
    other_app.labels["minipaas.operation"] = OP2
    r = client.post(f"/apps/{SLUG}/operations/{OP2}/cleanup", headers=AUTH)
    assert r.json() == {"removed": [name_of("db")]}
    assert set(runtime.fake.container_objs) == {name_of(), "otra"}


def test_cleanup_invalid_operation(client):
    r = client.post(f"/apps/{SLUG}/operations/no-es-uuid/cleanup", headers=AUTH)
    assert r.status_code == 400


def test_delete_app_removes_containers_and_networks(client, runtime):
    prepare(client)
    create(client)
    add_foreign(runtime, "otra", owned_labels(**{"minipaas.app": "otra-app"}))
    r = client.delete(f"/apps/{SLUG}", headers=AUTH)
    assert r.status_code == 200
    assert len(r.json()["removed"]) == 3
    assert set(runtime.fake.container_objs) == {"otra"}
    assert runtime.fake.network_objs == {}


# --- errores de Docker ------------------------------------------------------------------


def test_docker_unavailable_is_503(client, runtime):
    runtime.error = RequestsConnectionError("sin conexión")
    r = client.get(f"/apps/{SLUG}/containers", headers=AUTH)
    assert r.status_code == 503
    assert r.json()["code"] == "docker_unavailable"


def test_docker_exception_is_503(client, runtime):
    runtime.error = docker.errors.DockerException("sin socket")
    assert client.get("/catalog", headers=AUTH).status_code == 503


def test_docker_api_error_is_502(client, runtime):
    prepare(client)
    runtime.fake.containers.list = lambda **_: (_ for _ in ()).throw(
        docker.errors.APIError("boom", explanation="fallo en /var/lib/docker/x/y")
    )
    r = client.get(f"/apps/{SLUG}/containers", headers=AUTH)
    assert r.status_code == 502
    assert "/var/lib" not in r.json()["detail"]


def test_deepcopy_guard():
    # Los valores de body() no se comparten entre tests (cada llamada crea un diccionario nuevo).
    assert copy.deepcopy(body()) == body()
    assert uuid.UUID(OP).version == 4
