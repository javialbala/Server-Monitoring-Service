"""Política de seguridad y operaciones del agente (ADR-002, ADR-017, ADR-029).

Toda la lógica que decide QUÉ se puede hacer con Docker vive aquí; `main.py` solo traduce HTTP.
Reglas que se aplican en cada operación:

- Lo único que llega del control plane son identificadores del catálogo y valores validados; la
  configuración real del contenedor (imagen, usuario, límites, red...) sale del catálogo.
- Solo se opera sobre recursos con las etiquetas de propiedad de ESTA instancia y de la
  aplicación de la ruta. Nunca basta con el nombre.
- No hay `exec`, `build`, montajes, `privileged`, dispositivos ni acceso al socket para las apps.
"""

import logging
import secrets
import threading
from collections import defaultdict

import docker.errors
from docker.types import LogConfig
from requests.exceptions import ReadTimeout

from minipaas.agent.config import AgentSettings
from minipaas.agent.docker_runtime import DockerRuntime
from minipaas.agent.errors import AgentError, conflict, invalid_request, not_found
from minipaas.common.agent_protocol import (
    CatalogEntryInfo,
    CatalogInfo,
    ContainerInfo,
    CreateContainerRequest,
    EnsureImageResponse,
    ProbeResponse,
)
from minipaas.common.catalog import (
    PROBE_IMAGE_REF,
    PROBE_USER,
    CatalogEntry,
    CatalogError,
    ServiceConfig,
    docker_architecture,
    enabled_entries,
    get_entry,
    validate_service_config,
)
from minipaas.common.naming import (
    LABEL_APP,
    LABEL_APP_ID,
    LABEL_CATALOG,
    LABEL_INSTANCE,
    LABEL_INTERNAL_PORT,
    LABEL_MANAGED,
    LABEL_OPERATION,
    LABEL_REVISION,
    LABEL_ROLE,
    LABEL_SERVICE,
    OPERATION_ID_RE,
    RESOURCE_PREFIX,
    container_name,
    edge_network_name,
    internal_network_name,
    is_valid_service_name,
    is_valid_slug,
)

logger = logging.getLogger("minipaas.agent")

ROLE_SERVICE = "service"
ROLE_PROBE = "probe"
ROLE_NET_INTERNAL = "network-internal"
ROLE_NET_EDGE = "network-edge"

NETWORK_NOT_READY = "La red de la aplicación no está preparada"
IMAGE_NOT_READY = "La imagen no está descargada o no coincide con el digest autorizado"
# El SDK de alto nivel no admite `stop_timeout` al crear: el plazo se indica al parar.
STOP_TIMEOUT_SECONDS = 10
MASQUERADE_OPTION = "com.docker.network.bridge.enable_ip_masquerade"


class AgentOperations:
    def __init__(self, settings: AgentSettings, runtime: DockerRuntime) -> None:
        self._settings = settings
        self._runtime = runtime
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_guard = threading.Lock()

    # ------------------------------------------------------------------ utilidades

    @property
    def _client(self):
        return self._runtime.client()

    def _lock(self, slug: str) -> threading.Lock:
        # Un candado por aplicación: dos peticiones sobre la misma app no se pisan.
        with self._locks_guard:
            return self._locks[slug]

    def _check_slug(self, slug: str) -> None:
        if not is_valid_slug(slug):
            raise invalid_request("Identificador de aplicación no válido")

    def _base_labels(self, slug: str, role: str) -> dict[str, str]:
        return {
            LABEL_MANAGED: "true",
            LABEL_INSTANCE: self._settings.instance,
            LABEL_APP: slug,
            LABEL_ROLE: role,
        }

    def _is_owned(self, labels: dict | None, slug: str, roles: tuple[str, ...]) -> bool:
        labels = labels or {}
        return (
            labels.get(LABEL_MANAGED) == "true"
            and labels.get(LABEL_INSTANCE) == self._settings.instance
            and labels.get(LABEL_APP) == slug
            and labels.get(LABEL_ROLE) in roles
        )

    def _get_container(self, slug: str, name: str, roles=(ROLE_SERVICE,)):
        """Devuelve el contenedor si es propio; si no, 404 (exista o no)."""
        self._check_slug(slug)
        if not name.startswith(f"{RESOURCE_PREFIX}{self._settings.instance}-{slug}-"):
            raise not_found()
        try:
            container = self._client.containers.get(name)
        except docker.errors.NotFound:
            raise not_found() from None
        if container.name != name or not self._is_owned(container.labels, slug, roles):
            raise not_found()
        return container

    def _get_network(self, slug: str, name: str, role: str):
        """Devuelve la red si existe y es propia, None si no existe; 409 si existe y es ajena."""
        try:
            network = self._client.networks.get(name)
        except docker.errors.NotFound:
            return None
        if network.attrs.get("Name") != name or not self._is_owned(
            network.attrs.get("Labels"), slug, (role,)
        ):
            raise conflict(f"Ya existe un recurso ajeno con el nombre {name}")
        return network

    def _owned_containers(self, slug: str, roles: tuple[str, ...], operation: str | None = None):
        labels = [
            f"{LABEL_MANAGED}=true",
            f"{LABEL_INSTANCE}={self._settings.instance}",
            f"{LABEL_APP}={slug}",
        ]
        if operation is not None:
            labels.append(f"{LABEL_OPERATION}={operation}")
        found = self._client.containers.list(all=True, filters={"label": labels})
        # Se vuelve a comprobar en código: el filtro de Docker no es la barrera de seguridad.
        return [c for c in found if self._is_owned(c.labels, slug, roles)]

    def _info(self, container) -> ContainerInfo:
        labels = container.labels
        state = container.attrs["State"]
        started_at = state.get("StartedAt")
        host_port, address = None, None
        bindings = container.attrs["HostConfig"].get("PortBindings") or {}
        for binding in bindings.get(f"{labels[LABEL_INTERNAL_PORT]}/tcp") or []:
            host_port, address = int(binding["HostPort"]), binding["HostIp"]
        return ContainerInfo(
            name=container.name,
            service_name=labels[LABEL_SERVICE],
            revision=int(labels[LABEL_REVISION]),
            operation_id=labels[LABEL_OPERATION],
            catalog_id=labels[LABEL_CATALOG],
            state=state["Status"],
            exit_code=state.get("ExitCode") if state["Status"] in ("exited", "dead") else None,
            oom_killed=bool(state.get("OOMKilled")),
            restart_count=int(container.attrs.get("RestartCount") or 0),
            started_at=None if not started_at or started_at.startswith("0001") else started_at,
            host_port=host_port,
            publish_address=address,
        )

    # ------------------------------------------------------------------ catálogo e imágenes

    def _host_architecture(self) -> str:
        return docker_architecture(self._client.info()["Architecture"])

    def catalog(self) -> CatalogInfo:
        entries = enabled_entries(self._settings.enable_test_catalog)
        return CatalogInfo(
            instance=self._settings.instance,
            architecture=self._host_architecture(),
            publish_address=self._settings.publish_address,
            entries=[
                CatalogEntryInfo(
                    id=e.id,
                    digest=e.digest,
                    architectures=list(e.architectures),
                    test_only=e.test_only,
                )
                for e in entries
            ],
        )

    def _entry(self, catalog_id: str) -> CatalogEntry:
        try:
            return get_entry(catalog_id, include_test=self._settings.enable_test_catalog)
        except CatalogError as error:
            raise invalid_request(str(error)) from None

    def _local_image_matches(self, entry: CatalogEntry) -> bool:
        """True si la imagen está descargada Y su digest es el autorizado."""
        try:
            image = self._client.images.get(entry.image_ref)
        except docker.errors.ImageNotFound:
            return False
        return entry.image_ref in (image.attrs.get("RepoDigests") or [])

    def ensure_image(self, catalog_id: str) -> EnsureImageResponse:
        entry = self._entry(catalog_id)
        pulled = False
        if not self._has_image(entry.image_ref):
            # Siempre por digest: Docker verifica que el contenido coincide.
            self._client.images.pull(entry.image_ref)
            pulled = True
            logger.info("Imagen descargada para %s", entry.id)
        if not self._local_image_matches(entry):
            raise AgentError(502, "docker_error", IMAGE_NOT_READY)
        if not self._has_image(PROBE_IMAGE_REF):
            self._client.images.pull(PROBE_IMAGE_REF)
        return EnsureImageResponse(catalog_id=entry.id, image_ref=entry.image_ref, pulled=pulled)

    def _has_image(self, ref: str) -> bool:
        try:
            self._client.images.get(ref)
        except docker.errors.ImageNotFound:
            return False
        return True

    # ------------------------------------------------------------------ redes

    def ensure_networks(self, slug: str, app_id: int) -> list[str]:
        self._check_slug(slug)
        with self._lock(slug):
            internal = internal_network_name(self._settings.instance, slug)
            edge = edge_network_name(self._settings.instance, slug)
            self._ensure_network(slug, app_id, internal, ROLE_NET_INTERNAL)
            self._ensure_network(slug, app_id, edge, ROLE_NET_EDGE)
        return [internal, edge]

    def _ensure_network(self, slug: str, app_id: int, name: str, role: str) -> None:
        if self._get_network(slug, name, role) is not None:
            return
        labels = {**self._base_labels(slug, role), LABEL_APP_ID: str(app_id)}
        if role == ROLE_NET_INTERNAL:
            # Sin salida a Internet y sin puertos publicables.
            self._client.networks.create(name, driver="bridge", internal=True, labels=labels)
        else:
            # Bridge normal (Docker no publica puertos de redes `internal`), pero sin NAT de
            # salida: el contenedor puede recibir desde el host, no salir a Internet (ADR-031).
            self._client.networks.create(
                name, driver="bridge", options={MASQUERADE_OPTION: "false"}, labels=labels
            )

    def delete_networks(self, slug: str) -> list[str]:
        self._check_slug(slug)
        with self._lock(slug):
            networks = self._existing_networks(slug)
            for network in networks:
                network.reload()
                if network.attrs.get("Containers"):
                    raise conflict("La aplicación aún tiene contenedores conectados a su red")
            names = [n.attrs["Name"] for n in networks]
            for network in networks:
                network.remove()
        return names

    def _existing_networks(self, slug: str) -> list:
        instance = self._settings.instance
        wanted = (
            (internal_network_name(instance, slug), ROLE_NET_INTERNAL),
            (edge_network_name(instance, slug), ROLE_NET_EDGE),
        )
        found = (self._get_network(slug, name, role) for name, role in wanted)
        return [network for network in found if network is not None]

    def _require_network(self, slug: str, name: str, role: str) -> None:
        # Un recurso ajeno con ese nombre también cuenta como «no preparada».
        try:
            network = self._get_network(slug, name, role)
        except AgentError:
            network = None
        if network is None:
            raise conflict(NETWORK_NOT_READY)

    # ------------------------------------------------------------------ contenedores

    def create_container(
        self, slug: str, request: CreateContainerRequest
    ) -> tuple[ContainerInfo, bool]:
        """Crea un contenedor sin arrancarlo. Devuelve (info, creado)."""
        service = request.service
        if slug != request.app_slug:
            raise invalid_request("El identificador de la ruta no coincide con el del cuerpo")
        self._check_slug(slug)
        if not is_valid_service_name(service.service_name):
            raise invalid_request("Nombre de servicio no válido")
        entry = self._entry(service.catalog_id)
        try:
            config = validate_service_config(
                entry,
                internal_port=service.internal_port,
                host_port=service.host_port,
                env=service.env,
                memory_mb=service.memory_mb,
                cpus=service.cpus,
                architecture=self._host_architecture(),
            )
        except CatalogError as error:
            raise invalid_request(str(error)) from None

        instance = self._settings.instance
        name = container_name(instance, slug, service.service_name, request.revision)
        with self._lock(slug):
            existing = self._existing_same_operation(slug, name, request.operation_id)
            if existing is not None:
                return existing, False
            self._require_network(slug, internal_network_name(instance, slug), ROLE_NET_INTERNAL)
            if config.host_port is not None:
                self._require_network(slug, edge_network_name(instance, slug), ROLE_NET_EDGE)
            if not self._local_image_matches(entry):
                raise conflict(IMAGE_NOT_READY)
            container = self._create(slug, name, request, entry, config)
            return self._info(container), True

    def _existing_same_operation(
        self, slug: str, name: str, operation_id: str
    ) -> ContainerInfo | None:
        """Idempotencia: misma operación -> el mismo contenedor; otra cosa con ese nombre -> 409."""
        try:
            existing = self._client.containers.get(name)
        except docker.errors.NotFound:
            return None
        labels = existing.labels or {}
        if self._is_owned(labels, slug, (ROLE_SERVICE,)) and (
            labels.get(LABEL_OPERATION) == operation_id
        ):
            return self._info(existing)
        raise conflict("Ya existe un contenedor con ese nombre")

    def _create(self, slug, name, request, entry, config: ServiceConfig):
        """Construye el contenedor SOLO con valores del catálogo y de la configuración validada."""
        service = request.service
        instance = self._settings.instance
        internal = internal_network_name(instance, slug)
        labels = {
            **self._base_labels(slug, ROLE_SERVICE),
            LABEL_APP_ID: str(request.app_id),
            LABEL_SERVICE: service.service_name,
            LABEL_REVISION: str(request.revision),
            LABEL_OPERATION: request.operation_id,
            LABEL_CATALOG: entry.id,
            LABEL_INTERNAL_PORT: str(config.internal_port),
        }
        ports = None
        if config.host_port is not None:
            # La dirección sale de la configuración del agente, nunca de la petición.
            ports = {
                f"{config.internal_port}/tcp": (self._settings.publish_address, config.host_port)
            }
        memory = f"{config.memory_mb}m"
        client = self._client
        endpoint = client.api.create_endpoint_config(aliases=[service.service_name])
        container = client.containers.create(
            entry.image_ref,
            name=name,
            hostname=service.service_name,
            user=entry.user,
            environment=config.env_dict(),  # sus valores no se registran en ningún log
            labels=labels,
            read_only=True,
            tmpfs={path: f"rw,noexec,nosuid,size={mb}m" for path, mb in entry.tmpfs},
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            privileged=False,
            mem_limit=memory,
            memswap_limit=memory,  # igual que mem_limit: sin swap
            nano_cpus=int(config.cpus * 1e9),
            pids_limit=entry.pids_limit,
            # Las políticas de reinicio son de la Fase 9; hasta entonces nada se reinicia solo.
            restart_policy={"Name": "no"},
            log_config=LogConfig(
                type=LogConfig.types.JSON, config={"max-size": "5m", "max-file": "2"}
            ),
            ports=ports,
            network=internal,
            networking_config={internal: endpoint},
        )
        try:
            if config.host_port is not None:
                edge = client.networks.get(edge_network_name(instance, slug))
                edge.connect(container)
            container.reload()
        except Exception:
            container.remove(force=True)  # no dejar un contenedor a medio configurar
            raise
        logger.info("Contenedor creado: %s", name)
        return container

    def list_containers(self, slug: str) -> list[ContainerInfo]:
        self._check_slug(slug)
        return [self._info(c) for c in self._owned_containers(slug, (ROLE_SERVICE,))]

    def start_container(self, slug: str, name: str) -> ContainerInfo:
        container = self._get_container(slug, name)
        with self._lock(slug):
            container.reload()
            if container.attrs["State"]["Status"] != "running":
                container.start()
                container.reload()
        return self._info(container)

    def stop_container(self, slug: str, name: str) -> ContainerInfo:
        container = self._get_container(slug, name)
        with self._lock(slug):
            container.reload()
            if container.attrs["State"]["Status"] in ("running", "restarting", "paused"):
                container.stop(timeout=STOP_TIMEOUT_SECONDS)
                container.reload()
        return self._info(container)

    def remove_container(self, slug: str, name: str) -> None:
        container = self._get_container(slug, name)
        with self._lock(slug):
            container.remove(force=True)
        logger.info("Contenedor eliminado: %s", name)

    def cleanup_operation(self, slug: str, operation_id: str) -> list[str]:
        """Elimina lo que dejó una operación (servicios y sondas) y nada más."""
        self._check_slug(slug)
        if not OPERATION_ID_RE.match(operation_id):
            raise invalid_request("Identificador de operación no válido")
        with self._lock(slug):
            found = self._owned_containers(slug, (ROLE_SERVICE, ROLE_PROBE), operation_id)
            return self._remove_all(found)

    def delete_app(self, slug: str) -> list[str]:
        """Elimina todos los contenedores propios de la aplicación y después sus redes."""
        self._check_slug(slug)
        with self._lock(slug):
            removed = self._remove_all(self._owned_containers(slug, (ROLE_SERVICE, ROLE_PROBE)))
            for network in self._existing_networks(slug):
                name = network.attrs["Name"]
                network.remove()
                removed.append(name)
        return removed

    @staticmethod
    def _remove_all(containers) -> list[str]:
        names = []
        for container in containers:
            container.remove(force=True)
            names.append(container.name)
        return names

    # ------------------------------------------------------------------ sonda de salud

    def probe(self, slug: str, name: str) -> ProbeResponse:
        target = self._get_container(slug, name)
        target.reload()
        if target.attrs["State"]["Status"] != "running":
            return ProbeResponse(healthy=False, detail="El servicio no está en ejecución")
        # La ruta de salud sale del catálogo, a partir de la etiqueta del contenedor: el cliente
        # no puede indicar URL ni comando.
        entry = self._entry(target.labels[LABEL_CATALOG])
        labels = target.labels
        url = f"http://{labels[LABEL_SERVICE]}:{labels[LABEL_INTERNAL_PORT]}{entry.health.path}"
        timeout = entry.health.timeout_seconds
        healthy = self._run_probe(slug, name, labels[LABEL_OPERATION], url, timeout)
        detail = "Responde correctamente" if healthy else "No responde o responde con error"
        return ProbeResponse(healthy=healthy, detail=detail)

    def _run_probe(self, slug: str, target_name: str, operation: str, url: str, timeout: int):
        """Ejecuta `wget` en un contenedor efímero dentro de la red interna de la aplicación."""
        client = self._client
        labels = {**self._base_labels(slug, ROLE_PROBE), LABEL_OPERATION: operation}
        try:
            probe = client.containers.create(
                PROBE_IMAGE_REF,
                name=f"{target_name}-probe-{secrets.token_hex(4)}",
                entrypoint=["wget"],
                command=["-q", "-T", str(timeout), "-O", "/dev/null", url],
                user=PROBE_USER,
                labels=labels,
                network=internal_network_name(self._settings.instance, slug),
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                privileged=False,
                mem_limit="16m",
                memswap_limit="16m",
                pids_limit=16,
                restart_policy={"Name": "no"},
            )
        except docker.errors.ImageNotFound:
            raise conflict(IMAGE_NOT_READY) from None
        try:
            probe.start()
            result = probe.wait(timeout=timeout + 5)
            return result.get("StatusCode") == 0
        except ReadTimeout:
            return False
        finally:
            probe.remove(force=True)  # la sonda nunca se queda
