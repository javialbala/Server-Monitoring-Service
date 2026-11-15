"""AgentOperations contra Docker REAL, con la instancia `itest` (no toca `dev` ni nada ajeno).

Las imágenes del catálogo deben estar ya descargadas. Al terminar se elimina todo lo que tenga
la etiqueta `minipaas.instance=itest`, aunque el test falle.
"""

import secrets
import socket
import time
import uuid

import docker
import httpx
import pytest

from minipaas.agent.config import AgentSettings
from minipaas.agent.docker_runtime import DockerRuntime
from minipaas.agent.errors import AgentError
from minipaas.agent.operations import AgentOperations
from minipaas.common.agent_protocol import CreateContainerRequest
from minipaas.common.catalog import NGINX_STATIC, PROBE_IMAGE_REF, WHOAMI
from minipaas.common.naming import container_name, edge_network_name, internal_network_name

pytestmark = pytest.mark.integration

INSTANCE = "itest"
INSTANCE_FILTER = {"label": f"minipaas.instance={INSTANCE}"}


def _remove_itest_resources(client) -> None:
    for container in client.containers.list(all=True, filters=INSTANCE_FILTER):
        container.remove(force=True)
    for network in client.networks.list(filters=INSTANCE_FILTER):
        network.remove()


@pytest.fixture
def client():
    return docker.from_env()


@pytest.fixture
def ops(client):
    """Agente real con la instancia `itest`; verifica que no cambia nada ajeno."""
    _remove_itest_resources(client)
    foreign_before = {c.id for c in client.containers.list(all=True)}
    settings = AgentSettings(token_file="x", instance=INSTANCE, enable_test_catalog=True)
    try:
        yield AgentOperations(settings, DockerRuntime())
    finally:
        _remove_itest_resources(client)
        assert {c.id for c in client.containers.list(all=True)} == foreign_before


@pytest.fixture
def slug():
    return f"itest-{secrets.token_hex(3)}"


def free_port(exclude: set[int] = frozenset()) -> int:
    for port in range(20900, 21000):
        if port in exclude:
            continue
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No hay puertos libres en 20900-20999")


def make_request(slug, service, catalog_id, operation=None, **overrides):
    entry = {"whoami": WHOAMI, "nginx-static": NGINX_STATIC}.get(catalog_id, NGINX_STATIC)
    spec = {
        "service_name": service,
        "catalog_id": catalog_id,
        "internal_port": entry.default_internal_port,
        "memory_mb": int(entry.memory_mb.default),
        "cpus": entry.cpus.default,
    }
    spec.update(overrides)
    return CreateContainerRequest.model_validate(
        {
            "operation_id": operation or str(uuid.uuid4()),
            "app_id": 1,
            "app_slug": slug,
            "revision": 1,
            "service": spec,
        }
    )


def wait_for(condition, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.5)
    return False


def run_wget(client, network, url) -> int:
    """Ejecuta wget en un contenedor efímero de la instancia de prueba; devuelve su código."""
    container = client.containers.create(
        PROBE_IMAGE_REF,
        entrypoint=["wget"],
        command=["-q", "-T", "3", "-O", "/dev/null", url],
        network=network,
        labels={"minipaas.instance": INSTANCE},
    )
    try:
        container.start()
        return container.wait(timeout=20)["StatusCode"]
    finally:
        container.remove(force=True)


def test_ensure_image_authorized_entries(ops):
    for entry in (WHOAMI, NGINX_STATIC):
        result = ops.ensure_image(entry.id)
        assert result.pulled is False
        assert result.image_ref == entry.image_ref
    with pytest.raises(AgentError) as info:
        ops.ensure_image("ubuntu")
    assert info.value.status == 400


def test_full_deployment_flow(ops, client, slug):
    other_slug = f"itest-{secrets.token_hex(3)}"
    port = free_port()
    internal = internal_network_name(INSTANCE, slug)
    edge = edge_network_name(INSTANCE, slug)

    # Redes: internas sin salida; edge sin masquerade; con etiquetas de propiedad.
    assert ops.ensure_networks(slug, 1) == [internal, edge]
    assert ops.ensure_networks(slug, 1) == [internal, edge]  # idempotente
    net_internal = client.networks.get(internal).attrs
    net_edge = client.networks.get(edge).attrs
    assert net_internal["Internal"] is True
    assert net_edge["Internal"] is False
    assert net_edge["Options"]["com.docker.network.bridge.enable_ip_masquerade"] == "false"
    assert net_internal["Labels"]["minipaas.managed"] == "true"
    assert net_internal["Labels"]["minipaas.instance"] == INSTANCE
    assert net_edge["Labels"]["minipaas.role"] == "network-edge"

    # Dos servicios: whoami publicado y nginx solo interno.
    web_req = make_request(slug, "web", "whoami", host_port=port)
    db_req = make_request(slug, "front", "nginx-static")
    web, created = ops.create_container(slug, web_req)
    assert created is True
    front, _ = ops.create_container(slug, db_req)
    assert ops.create_container(slug, web_req)[1] is False  # idempotente

    # Inspección de seguridad del contenedor real.
    attrs = client.containers.get(web.name).attrs
    host_config = attrs["HostConfig"]
    assert attrs["Mounts"] == []
    assert not host_config.get("Binds")
    assert host_config["Privileged"] is False
    assert host_config["ReadonlyRootfs"] is True
    assert host_config["CapDrop"] == ["ALL"]
    assert "no-new-privileges:true" in host_config["SecurityOpt"]
    assert host_config["Memory"] == host_config["MemorySwap"] == 32 * 1024 * 1024
    assert host_config["NanoCpus"] == 250_000_000
    assert host_config["PidsLimit"] == WHOAMI.pids_limit
    assert host_config["Devices"] in (None, [])
    assert attrs["Config"]["User"] == WHOAMI.user
    assert set(attrs["NetworkSettings"]["Networks"]) == {internal, edge}
    front_attrs = client.containers.get(front.name).attrs
    assert set(front_attrs["NetworkSettings"]["Networks"]) == {internal}
    assert front_attrs["HostConfig"]["Tmpfs"]["/tmp"].startswith("rw,noexec,nosuid")  # noqa: S108

    # Arranque, estado real y sondas.
    assert ops.start_container(slug, web.name).state == "running"
    assert ops.start_container(slug, web.name).state == "running"  # no-op
    assert ops.start_container(slug, front.name).state == "running"
    listed = {c.name: c for c in ops.list_containers(slug)}
    assert listed[web.name].host_port == port
    assert listed[web.name].publish_address == "127.0.0.1"
    assert listed[front.name].host_port is None
    for name in (web.name, front.name):
        assert wait_for(lambda name=name: ops.probe(slug, name).healthy)

    # Publicación: el host llega al puerto publicado.
    assert wait_for(lambda: httpx.get(f"http://127.0.0.1:{port}/health", timeout=3).is_success)

    # Aislamiento: otra app no alcanza el servicio (ni por nombre ni por IP) y no hay Internet.
    ops.ensure_networks(other_slug, 2)
    other_net = internal_network_name(INSTANCE, other_slug)
    ip = attrs_ip = client.containers.get(web.name).attrs["NetworkSettings"]["Networks"][internal][
        "IPAddress"
    ]
    assert attrs_ip
    assert run_wget(client, internal, "http://web:80/health") == 0  # control positivo
    assert run_wget(client, other_net, "http://web:80/health") != 0
    assert run_wget(client, other_net, f"http://{ip}:80/health") != 0
    assert run_wget(client, internal, "http://1.1.1.1/") != 0

    # Parar y volver a arrancar.
    assert ops.stop_container(slug, web.name).state == "exited"
    assert ops.stop_container(slug, web.name).state == "exited"  # no-op
    assert ops.probe(slug, web.name).healthy is False
    assert ops.start_container(slug, web.name).state == "running"

    # Cleanup de operación: solo los de esa operación.
    ops.cleanup_operation(slug, web_req.operation_id)
    assert [c.name for c in ops.list_containers(slug)] == [front.name]

    # Con contenedores conectados no se borran las redes; DELETE de la app no deja restos.
    with pytest.raises(AgentError) as info:
        ops.delete_networks(slug)
    assert info.value.status == 409
    removed = ops.delete_app(slug)
    assert set(removed) == {front.name, internal, edge}
    leftovers = {"label": f"minipaas.app={slug}"}
    assert client.containers.list(all=True, filters=leftovers) == []
    assert client.networks.list(filters=leftovers) == []
    # La otra app sigue intacta.
    assert client.networks.get(other_net)
    assert ops.delete_networks(other_slug) == [other_net, edge_network_name(INSTANCE, other_slug)]


def test_crash_service_exits_with_error(ops, slug):
    ops.ensure_networks(slug, 1)
    request = make_request(slug, "crash", "test-crash")
    info, _ = ops.create_container(slug, request)
    ops.start_container(slug, info.name)

    def exited():
        return ops.list_containers(slug)[0].state == "exited"

    assert wait_for(exited)
    final = ops.list_containers(slug)[0]
    assert final.exit_code not in (0, None)
    assert ops.probe(slug, info.name).healthy is False


def test_unhealthy_service_starts_but_probe_fails(ops, slug):
    ops.ensure_networks(slug, 1)
    info, _ = ops.create_container(slug, make_request(slug, "sick", "test-unhealthy"))
    assert ops.start_container(slug, info.name).state == "running"
    time.sleep(2)
    assert ops.probe(slug, info.name).healthy is False


def test_foreign_container_is_not_touched(ops, client, slug):
    """Un contenedor sin etiquetas de MiniPaaS no se puede parar ni borrar mediante el agente."""
    name = container_name(INSTANCE, slug, "ajeno", 1)
    foreign = client.containers.run(
        PROBE_IMAGE_REF,
        name=name,
        entrypoint=["sleep", "120"],
        detach=True,
        labels={"minipaas.instance": INSTANCE},  # solo para que la limpieza lo encuentre
    )
    for action in (ops.stop_container, ops.remove_container, ops.start_container, ops.probe):
        with pytest.raises(AgentError) as info:
            action(slug, name)
        assert info.value.status == 404
    assert ops.delete_app(slug) == []
    assert ops.cleanup_operation(slug, str(uuid.uuid4())) == []
    foreign.reload()
    assert foreign.status == "running"


def test_agent_ignores_dev_instance(ops, client, slug):
    dev_ids = {
        c.id for c in client.containers.list(all=True, filters={"label": "minipaas.instance=dev"})
    }
    assert ops.list_containers("minipaas-dev") == []
    ops.delete_app(slug)
    now = {
        c.id for c in client.containers.list(all=True, filters={"label": "minipaas.instance=dev"})
    }
    assert now == dev_ids


def test_missing_network_blocks_creation(ops, slug):
    with pytest.raises(AgentError) as info:
        ops.create_container(slug, make_request(slug, "web", "whoami"))
    assert info.value.status == 409
