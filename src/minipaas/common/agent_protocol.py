"""Protocolo HTTP entre control plane y agente (ADR-029).

Define los cuerpos de petición y respuesta de la API interna del agente. Ambos lados usan estos
modelos: el control plane para construir peticiones y leer respuestas, el agente para validar lo
que recibe (`extra="forbid"`: cualquier campo desconocido se rechaza). Ningún modelo contiene
opciones de Docker: el agente construye la configuración real a partir del catálogo.

Rutas (todas exigen `Authorization: Bearer <token>`; errores como `ErrorBody`):

    GET    /health                                          estado del agente y de Docker
    GET    /catalog                                         CatalogInfo
    POST   /images/ensure                  EnsureImageRequest -> EnsureImageResponse
    POST   /apps/{slug}/networks           EnsureNetworksRequest -> NetworksResponse
    DELETE /apps/{slug}/networks                            NetworksResponse (409 si hay
                                                            contenedores)
    GET    /apps/{slug}/containers                          ContainersResponse
    POST   /apps/{slug}/containers         CreateContainerRequest -> ContainerInfo
                                           (201; 200 si ya existía con la misma operación)
    POST   /apps/{slug}/containers/{name}/start             ContainerInfo
    POST   /apps/{slug}/containers/{name}/stop              ContainerInfo
    DELETE /apps/{slug}/containers/{name}                   204
    POST   /apps/{slug}/containers/{name}/probe             ProbeResponse
    POST   /apps/{slug}/operations/{operation_id}/cleanup   RemovedResponse
    DELETE /apps/{slug}                                     RemovedResponse (contenedores y redes)

Códigos de error del agente: 400 `invalid_request` (catálogo/validación), 401 `unauthorized`,
404 `not_found` (no existe o no pertenece a MiniPaaS/instancia/aplicación), 409 `conflict`,
422 (validación de esquema), 502 `docker_error`, 503 `docker_unavailable`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from minipaas.common.catalog import HOST_PORT_MAX, HOST_PORT_MIN

_SLUG = r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$"
_SERVICE = r"^[a-z][a-z0-9-]{0,28}[a-z0-9]$"
_OPERATION = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_CATALOG_ID = r"^[a-z][a-z0-9-]{1,40}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ErrorBody(_Strict):
    detail: str
    code: str


class CatalogEntryInfo(_Strict):
    id: str
    digest: str
    architectures: list[str]
    test_only: bool


class CatalogInfo(_Strict):
    instance: str
    architecture: str  # del host, formato de manifiesto ("amd64")
    publish_address: str
    entries: list[CatalogEntryInfo]


class EnsureImageRequest(_Strict):
    catalog_id: str = Field(pattern=_CATALOG_ID)


class EnsureImageResponse(_Strict):
    catalog_id: str
    image_ref: str
    pulled: bool  # False si ya estaba descargada


class EnsureNetworksRequest(_Strict):
    app_id: int = Field(gt=0)


class NetworksResponse(_Strict):
    networks: list[str]


class ServiceSpec(_Strict):
    """Descripción de alto nivel de un servicio. NO es configuración de Docker (ADR-002)."""

    service_name: str = Field(pattern=_SERVICE)
    catalog_id: str = Field(pattern=_CATALOG_ID)
    internal_port: int = Field(ge=1, le=65535)
    host_port: int | None = Field(default=None, ge=HOST_PORT_MIN, le=HOST_PORT_MAX)
    env: dict[str, str] = Field(default_factory=dict)
    memory_mb: int = Field(ge=1, le=4096)
    cpus: float = Field(gt=0, le=8)


class CreateContainerRequest(_Strict):
    operation_id: str = Field(pattern=_OPERATION)
    app_id: int = Field(gt=0)
    app_slug: str = Field(pattern=_SLUG)
    revision: int = Field(ge=1, le=1_000_000)
    service: ServiceSpec


ContainerState = Literal["created", "running", "paused", "restarting", "removing", "exited", "dead"]


class ContainerInfo(_Strict):
    name: str
    service_name: str
    revision: int
    operation_id: str
    catalog_id: str
    state: ContainerState
    exit_code: int | None
    oom_killed: bool
    restart_count: int
    started_at: str | None
    host_port: int | None
    publish_address: str | None


class ContainersResponse(_Strict):
    containers: list[ContainerInfo]


class ProbeResponse(_Strict):
    healthy: bool
    detail: str  # resumen corto y no sensible, p. ej. "HTTP 200" o "sin respuesta"


class RemovedResponse(_Strict):
    removed: list[str]


# Plazos del control plane para cada llamada (segundos). La descarga de una imagen puede tardar.
TIMEOUTS = {
    "default": 10.0,
    "ensure_image": 300.0,
    "create": 30.0,
    "start": 30.0,
    "stop": 30.0,
    "probe": 20.0,
    "remove": 30.0,
}
