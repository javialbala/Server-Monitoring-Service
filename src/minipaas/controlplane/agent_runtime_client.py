"""Cliente HTTP SÍNCRONO de la API interna del agente (protocolo en `common/agent_protocol.py`).

Lo usa el motor de despliegue, que corre en hilos de trabajo. Un método por ruta del agente;
las respuestas se validan con los mismos modelos que usa el agente. Los errores se traducen a
tres excepciones para que el motor no dependa de httpx:

- `AgentUnavailable`: no hay respuesta útil (conexión, plazo agotado, agente o Docker caídos).
  OJO: tras un plazo agotado Docker PUEDE haber ejecutado la acción; quien llama no debe
  suponer lo contrario.
- `AgentRejected`: el agente respondió 4xx (petición no válida, recurso inexistente, conflicto).
- `AgentDockerError`: el agente respondió 502 (Docker falló) o una respuesta ilegible.

Nunca se registra el token ni el entorno de los servicios.
"""

import httpx
from pydantic import BaseModel, ValidationError

from minipaas.common.agent_protocol import (
    TIMEOUTS,
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


class AgentError(Exception):
    """Base de los errores del agente."""


class AgentUnavailable(AgentError):  # noqa: N818  (nombre del diseño)
    pass


class AgentRejected(AgentError):
    def __init__(self, status: int, detail: str, code: str) -> None:
        super().__init__(f"{status} {code}: {detail}")
        self.status = status
        self.detail = detail
        self.code = code


class AgentDockerError(AgentError):
    pass


class AgentRuntimeClient:
    def __init__(
        self, base_url: str, token: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {token}"}, transport=transport
        )

    def close(self) -> None:
        self._client.close()

    # --- Catálogo, imágenes y redes -------------------------------------------------------

    def catalog(self) -> CatalogInfo:
        return self._call("GET", "/catalog", "default", CatalogInfo)

    def ensure_image(self, catalog_id: str) -> EnsureImageResponse:
        body = EnsureImageRequest(catalog_id=catalog_id)
        return self._call("POST", "/images/ensure", "ensure_image", EnsureImageResponse, body)

    def ensure_networks(self, slug: str, app_id: int) -> NetworksResponse:
        body = EnsureNetworksRequest(app_id=app_id)
        return self._call("POST", f"/apps/{slug}/networks", "default", NetworksResponse, body)

    def delete_networks(self, slug: str) -> NetworksResponse:
        return self._call("DELETE", f"/apps/{slug}/networks", "remove", NetworksResponse)

    # --- Contenedores ---------------------------------------------------------------------

    def list_containers(self, slug: str) -> list[ContainerInfo]:
        return self._call(
            "GET", f"/apps/{slug}/containers", "default", ContainersResponse
        ).containers

    def create_container(self, slug: str, request: CreateContainerRequest) -> ContainerInfo:
        return self._call("POST", f"/apps/{slug}/containers", "create", ContainerInfo, request)

    def start_container(self, slug: str, name: str) -> ContainerInfo:
        return self._call("POST", f"/apps/{slug}/containers/{name}/start", "start", ContainerInfo)

    def stop_container(self, slug: str, name: str) -> ContainerInfo:
        return self._call("POST", f"/apps/{slug}/containers/{name}/stop", "stop", ContainerInfo)

    def probe(self, slug: str, name: str) -> ProbeResponse:
        return self._call("POST", f"/apps/{slug}/containers/{name}/probe", "probe", ProbeResponse)

    # --- Limpieza -------------------------------------------------------------------------

    def cleanup_operation(self, slug: str, operation_id: str) -> RemovedResponse:
        path = f"/apps/{slug}/operations/{operation_id}/cleanup"
        return self._call("POST", path, "remove", RemovedResponse)

    def delete_app(self, slug: str) -> RemovedResponse:
        return self._call("DELETE", f"/apps/{slug}", "remove", RemovedResponse)

    # --- Interno --------------------------------------------------------------------------

    def _call[T: BaseModel](
        self,
        method: str,
        path: str,
        operation: str,
        response_model: type[T],
        body: BaseModel | None = None,
    ) -> T:
        content = body.model_dump_json() if body is not None else None
        headers = {"Content-Type": "application/json"} if content else None
        try:
            response = self._client.request(
                method, path, content=content, headers=headers, timeout=TIMEOUTS[operation]
            )
        except httpx.HTTPError as error:  # conexión, plazo agotado, protocolo...
            raise AgentUnavailable(f"sin respuesta del agente ({type(error).__name__})") from None
        if response.status_code >= 400:
            raise _error_for(response)
        try:
            return response_model.model_validate_json(response.content)
        except ValidationError:
            raise AgentDockerError("respuesta del agente no válida") from None


def _error_for(response: httpx.Response) -> AgentError:
    status = response.status_code
    try:
        data = response.json()
        detail, code = str(data["detail"])[:200], str(data["code"])
    except (ValueError, KeyError, TypeError):
        detail, code = f"respuesta HTTP {status}", "unknown"
    if status == 503:
        return AgentUnavailable(f"el agente no puede usar Docker ({detail})")
    if status < 500:
        return AgentRejected(status, detail, code)
    return AgentDockerError(detail)
