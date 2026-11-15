"""Agente falso en memoria: implementa el protocolo de `agent_protocol.py` sin Docker.

Se usa detrás de `httpx.MockTransport(fake.handler)`. Valida las peticiones con los mismos modelos
y con `validate_service_config` que el agente real, es idempotente por nombre + operación y permite
INYECTAR FALLOS para probar el motor de despliegue (ver `faults`).
"""

import re
from collections.abc import Callable

import httpx

from minipaas.common.agent_protocol import (
    CatalogEntryInfo,
    CatalogInfo,
    ContainerInfo,
    ContainersResponse,
    CreateContainerRequest,
    EnsureImageRequest,
    EnsureImageResponse,
    EnsureNetworksRequest,
    NetworksResponse,
    ProbeResponse,
    RemovedResponse,
)
from minipaas.common.catalog import (
    CatalogError,
    enabled_entries,
    get_entry,
    validate_service_config,
)
from minipaas.common.naming import container_name, edge_network_name, internal_network_name

TOKEN = "t" * 40
INSTANCE = "test"
ARCHITECTURE = "amd64"

# Rutas del protocolo (el nombre del patrón dice qué operación es).
ROUTES = [
    ("GET", r"/health", "health"),
    ("GET", r"/catalog", "catalog"),
    ("POST", r"/images/ensure", "ensure_image"),
    ("POST", r"/apps/(?P<slug>[^/]+)/networks", "ensure_networks"),
    ("DELETE", r"/apps/(?P<slug>[^/]+)/networks", "delete_networks"),
    ("GET", r"/apps/(?P<slug>[^/]+)/containers", "list_containers"),
    ("POST", r"/apps/(?P<slug>[^/]+)/containers", "create"),
    ("POST", r"/apps/(?P<slug>[^/]+)/containers/(?P<name>[^/]+)/start", "start"),
    ("POST", r"/apps/(?P<slug>[^/]+)/containers/(?P<name>[^/]+)/stop", "stop"),
    ("DELETE", r"/apps/(?P<slug>[^/]+)/containers/(?P<name>[^/]+)", "remove"),
    ("POST", r"/apps/(?P<slug>[^/]+)/containers/(?P<name>[^/]+)/probe", "probe"),
    ("POST", r"/apps/(?P<slug>[^/]+)/operations/(?P<op>[^/]+)/cleanup", "cleanup"),
    ("DELETE", r"/apps/(?P<slug>[^/]+)", "delete_app"),
]


class FakeAgent:
    """Estado en memoria + inyección de fallos.

    `faults` es un diccionario `tipo -> lista de (servicio, revisión)`; `None` en cualquiera de
    los dos significa «cualquiera». Tipos:

    - `pull`: falla la descarga de la imagen (el servicio no importa: usa `(catalog_id, None)`).
    - `create`: falla la creación del contenedor (502).
    - `crash`: al arrancar, el contenedor termina enseguida (exited, código 1).
    - `unhealthy`: la sonda nunca da sano.
    - `start_error`: falla el arranque (502).
    - `catalog_unknown`: el catálogo del agente no contiene ninguna imagen.
    - `timeout_after`: la acción SÍ se ejecuta pero el agente no contesta a tiempo (`create`).

    `down = True` simula el agente caído (conexión rechazada). `on_request` se llama antes de
    atender cada petición (`(método, ruta)`): permite bloquear un hilo desde un test.
    """

    def __init__(self) -> None:
        self.images: set[str] = set()
        self.networks: set[str] = set()  # slugs con redes creadas
        self.containers: dict[str, dict] = {}  # nombre -> datos
        self.calls: list[tuple[str, str]] = []  # (operación, ruta) de cada petición atendida
        self.faults: dict[str, list[tuple[str | None, int | None]]] = {}
        self.down = False
        self.on_request: Callable[[str, str], None] | None = None

    # --- API para los tests ---------------------------------------------------------------

    def fail(self, kind: str, service: str | None = None, revision: int | None = None) -> None:
        self.faults.setdefault(kind, []).append((service, revision))

    def clear_faults(self) -> None:
        self.faults.clear()

    def names(self, slug: str | None = None, operation: str | None = None) -> list[str]:
        return sorted(
            n
            for n, c in self.containers.items()
            if (slug is None or c["slug"] == slug)
            and (operation is None or c["operation_id"] == operation)
        )

    def state_of(self, name: str) -> str:
        return self.containers[name]["state"]

    def add_container(
        self, slug: str, service: str, revision: int, operation_id: str, state: str = "running"
    ) -> str:
        """Contenedor creado «por fuera» (p. ej. de una operación que nadie conoce)."""
        name = container_name(INSTANCE, slug, service, revision)
        data = self._container(name, slug, service, revision, operation_id, "whoami", state, None)
        self.containers[name] = data
        return name

    def count(self, operation: str) -> int:
        return sum(1 for op, _ in self.calls if op == operation)

    # --- Transporte -----------------------------------------------------------------------

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.on_request:  # antes de comprobar `down`: el hook puede «tirar» el agente
            self.on_request(request.method, request.url.path)
        if self.down:
            raise httpx.ConnectError("conexión rechazada", request=request)
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._error(401, "unauthorized", "Token no válido")
        path = request.url.path
        for method, pattern, operation in ROUTES:
            match = re.fullmatch(pattern, path)
            if match and method == request.method:
                self.calls.append((operation, path))
                return getattr(self, f"_{operation}")(request, **match.groupdict())
        return self._error(404, "not_found", "Ruta desconocida")

    # --- Rutas ----------------------------------------------------------------------------

    def _health(self, request):
        return httpx.Response(200, json={"status": "ok", "docker": {"reachable": True}})

    def _catalog(self, request):
        entries = [
            CatalogEntryInfo(
                id=e.id, digest=e.digest, architectures=list(e.architectures), test_only=e.test_only
            )
            for e in enabled_entries(True)
            if not self._hit("catalog_unknown", None, None)
        ]
        info = CatalogInfo(
            instance=INSTANCE,
            architecture=ARCHITECTURE,
            publish_address="127.0.0.1",
            entries=entries,
        )
        return self._ok(info)

    def _ensure_image(self, request):
        body = EnsureImageRequest.model_validate_json(request.content)
        if self._hit("pull", body.catalog_id, None):
            return self._error(502, "docker_error", "No se pudo descargar la imagen")
        entry = get_entry(body.catalog_id, include_test=True)
        pulled = entry.image_ref not in self.images
        self.images.add(entry.image_ref)
        return self._ok(
            EnsureImageResponse(catalog_id=entry.id, image_ref=entry.image_ref, pulled=pulled)
        )

    def _ensure_networks(self, request, slug):
        body = EnsureNetworksRequest.model_validate_json(request.content)
        assert body.app_id > 0
        self.networks.add(slug)
        names = [internal_network_name(INSTANCE, slug), edge_network_name(INSTANCE, slug)]
        return self._ok(NetworksResponse(networks=names))

    def _delete_networks(self, request, slug):
        if self.names(slug):
            return self._error(409, "conflict", "La aplicación tiene contenedores")
        self.networks.discard(slug)
        return self._ok(NetworksResponse(networks=[]))

    def _list_containers(self, request, slug):
        infos = [self._info(c) for c in self.containers.values() if c["slug"] == slug]
        return self._ok(ContainersResponse(containers=infos))

    def _create(self, request, slug):
        body = CreateContainerRequest.model_validate_json(request.content)
        service = body.service
        try:
            validate_service_config(
                get_entry(service.catalog_id, include_test=True),
                internal_port=service.internal_port,
                host_port=service.host_port,
                env=service.env,
                memory_mb=service.memory_mb,
                cpus=service.cpus,
                architecture=ARCHITECTURE,
            )
        except CatalogError as error:
            return self._error(400, "invalid_request", str(error))
        name = container_name(INSTANCE, slug, service.service_name, body.revision)
        existing = self.containers.get(name)
        if existing and existing["operation_id"] != body.operation_id:
            return self._error(409, "conflict", "Ya existe un contenedor con ese nombre")
        if existing:  # idempotencia: misma operación -> 200 sin duplicar
            return self._ok(self._info(existing))
        if self._hit("create", service.service_name, body.revision):
            return self._error(502, "docker_error", "No se pudo crear el contenedor")
        self.containers[name] = self._container(
            name,
            slug,
            service.service_name,
            body.revision,
            body.operation_id,
            service.catalog_id,
            "created",
            service.host_port,
        )
        if self._hit("timeout_after", "create", None):  # Docker lo hizo, pero no hay respuesta
            raise httpx.ReadTimeout("plazo agotado", request=request)
        return self._ok(self._info(self.containers[name]), status=201)

    def _start(self, request, slug, name):
        container = self._get(slug, name)
        if container is None:
            return self._error(404, "not_found", "Contenedor no encontrado")
        if self._hit("start_error", container["service"], container["revision"]):
            return self._error(502, "docker_error", "No se pudo arrancar el contenedor")
        if self._hit("crash", container["service"], container["revision"]):
            container.update(state="exited", exit_code=1)
        else:
            container.update(state="running", exit_code=None)
        return self._ok(self._info(container))

    def _stop(self, request, slug, name):
        container = self._get(slug, name)
        if container is None:
            return self._error(404, "not_found", "Contenedor no encontrado")
        container.update(state="exited", exit_code=0)
        return self._ok(self._info(container))

    def _remove(self, request, slug, name):
        if self._get(slug, name) is None:
            return self._error(404, "not_found", "Contenedor no encontrado")
        del self.containers[name]
        return httpx.Response(204)

    def _probe(self, request, slug, name):
        container = self._get(slug, name)
        if container is None:
            return self._error(404, "not_found", "Contenedor no encontrado")
        healthy = container["state"] == "running" and not self._hit(
            "unhealthy", container["service"], container["revision"]
        )
        return self._ok(
            ProbeResponse(healthy=healthy, detail="HTTP 200" if healthy else "sin respuesta")
        )

    def _cleanup(self, request, slug, op):
        names = self.names(slug, op)
        for name in names:
            del self.containers[name]
        return self._ok(RemovedResponse(removed=names))

    def _delete_app(self, request, slug):
        names = self.names(slug)
        for name in names:
            del self.containers[name]
        self.networks.discard(slug)
        return self._ok(RemovedResponse(removed=names))

    # --- Utilidades -----------------------------------------------------------------------

    def _hit(self, kind: str, service: str | None, revision: int | None) -> bool:
        return any(
            s in (None, service) and r in (None, revision) for s, r in self.faults.get(kind, [])
        )

    def _get(self, slug: str, name: str) -> dict | None:
        container = self.containers.get(name)
        return container if container and container["slug"] == slug else None

    @staticmethod
    def _container(name, slug, service, revision, operation_id, catalog_id, state, host_port):
        return {
            "name": name,
            "slug": slug,
            "service": service,
            "revision": revision,
            "operation_id": operation_id,
            "catalog_id": catalog_id,
            "state": state,
            "exit_code": None,
            "host_port": host_port,
        }

    @staticmethod
    def _info(c: dict) -> ContainerInfo:
        return ContainerInfo(
            name=c["name"],
            service_name=c["service"],
            revision=c["revision"],
            operation_id=c["operation_id"],
            catalog_id=c["catalog_id"],
            state=c["state"],
            exit_code=c["exit_code"],
            oom_killed=False,
            restart_count=0,
            started_at=None,
            host_port=c["host_port"],
            publish_address="127.0.0.1" if c["host_port"] else None,
        )

    @staticmethod
    def _ok(model, status: int = 200) -> httpx.Response:
        return httpx.Response(
            status, content=model.model_dump_json(), headers={"content-type": "application/json"}
        )

    @staticmethod
    def _error(status: int, code: str, detail: str) -> httpx.Response:
        return httpx.Response(status, json={"detail": detail, "code": code})
