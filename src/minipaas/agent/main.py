"""API interna del agente: autenticada con token y sin ningún endpoint genérico de Docker.

Aquí solo se traduce HTTP; las reglas de seguridad están en `operations.py`. Las rutas son
exactamente las de `minipaas.common.agent_protocol`.
"""

import hmac
from typing import Annotated

import docker.errors
from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from requests.exceptions import RequestException
from starlette.exceptions import HTTPException as StarletteHTTPException

from minipaas.agent.config import AgentSettings
from minipaas.agent.docker_runtime import DockerRuntime
from minipaas.agent.errors import AgentError, summarize_docker_error
from minipaas.agent.operations import AgentOperations
from minipaas.common.agent_protocol import (
    CatalogInfo,
    ContainerInfo,
    ContainersResponse,
    CreateContainerRequest,
    EnsureImageRequest,
    EnsureImageResponse,
    EnsureNetworksRequest,
    ErrorBody,
    NetworksResponse,
    ProbeResponse,
    RemovedResponse,
)
from minipaas.common.secrets import read_token

_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def _error(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(ErrorBody(detail=detail, code=code).model_dump(), status_code=status)


def create_app(settings: AgentSettings, runtime: DockerRuntime) -> FastAPI:
    token = read_token(settings.token_file)  # falla al arrancar si el token no es válido
    ops = AgentOperations(settings, runtime)

    def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = f"Bearer {token}"
        # compare_digest evita filtrar información por el tiempo de comparación.
        # Mismo error si falta o no coincide: no se revela cuál.
        if authorization is None or not hmac.compare_digest(
            authorization.encode(), expected.encode()
        ):
            raise AgentError(401, "unauthorized", "No autorizado")

    # Sin documentación OpenAPI. El token se exige en TODAS las rutas definidas.
    app = FastAPI(
        title="MiniPaaS agent",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(require_token)],
    )

    # --- errores: siempre con el formato ErrorBody ---

    @app.exception_handler(AgentError)
    def agent_error(_: Request, error: AgentError) -> JSONResponse:
        return _error(error.status, error.code, error.detail)

    @app.exception_handler(StarletteHTTPException)
    def http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(error.status_code, "error")
        return _error(error.status_code, code, "Ruta o método no disponible")

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        # Solo campo y motivo: nunca el valor recibido (podría ser una variable de entorno).
        fields = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        return _error(422, "validation_error", f"Petición no válida ({fields})"[:500])

    @app.exception_handler(docker.errors.NotFound)
    def docker_not_found(_: Request, __: docker.errors.NotFound) -> JSONResponse:
        return _error(404, "not_found", "Recurso no encontrado")

    @app.exception_handler(docker.errors.APIError)
    def docker_api_error(_: Request, error: docker.errors.APIError) -> JSONResponse:
        return _error(502, "docker_error", summarize_docker_error(error))

    @app.exception_handler(docker.errors.DockerException)
    @app.exception_handler(RequestException)
    def docker_unavailable(_: Request, __: Exception) -> JSONResponse:
        return _error(503, "docker_unavailable", "Docker no está disponible")

    # --- rutas ---

    @app.get("/health")
    def health() -> dict:
        status = runtime.ping()
        return {
            "status": "ok",
            "docker": {"reachable": status.reachable, "server_version": status.server_version},
        }

    @app.get("/catalog")
    def catalog() -> CatalogInfo:
        return ops.catalog()

    @app.post("/images/ensure")
    def ensure_image(body: EnsureImageRequest) -> EnsureImageResponse:
        return ops.ensure_image(body.catalog_id)

    @app.post("/apps/{slug}/networks")
    def ensure_networks(slug: str, body: EnsureNetworksRequest) -> NetworksResponse:
        return NetworksResponse(networks=ops.ensure_networks(slug, body.app_id))

    @app.delete("/apps/{slug}/networks")
    def delete_networks(slug: str) -> NetworksResponse:
        return NetworksResponse(networks=ops.delete_networks(slug))

    @app.get("/apps/{slug}/containers")
    def list_containers(slug: str) -> ContainersResponse:
        return ContainersResponse(containers=ops.list_containers(slug))

    @app.post("/apps/{slug}/containers", status_code=201)
    def create_container(
        slug: str, body: CreateContainerRequest, response: Response
    ) -> ContainerInfo:
        info, created = ops.create_container(slug, body)
        if not created:
            response.status_code = 200  # misma operación repetida: no se crea nada nuevo
        return info

    @app.post("/apps/{slug}/containers/{name}/start")
    def start_container(slug: str, name: str) -> ContainerInfo:
        return ops.start_container(slug, name)

    @app.post("/apps/{slug}/containers/{name}/stop")
    def stop_container(slug: str, name: str) -> ContainerInfo:
        return ops.stop_container(slug, name)

    @app.delete("/apps/{slug}/containers/{name}", status_code=204)
    def remove_container(slug: str, name: str) -> Response:
        ops.remove_container(slug, name)
        return Response(status_code=204)

    @app.post("/apps/{slug}/containers/{name}/probe")
    def probe(slug: str, name: str) -> ProbeResponse:
        return ops.probe(slug, name)

    @app.post("/apps/{slug}/operations/{operation_id}/cleanup")
    def cleanup(slug: str, operation_id: str) -> RemovedResponse:
        return RemovedResponse(removed=ops.cleanup_operation(slug, operation_id))

    @app.delete("/apps/{slug}")
    def delete_app(slug: str) -> RemovedResponse:
        return RemovedResponse(removed=ops.delete_app(slug))

    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`: solo aquí se exige el entorno real."""
    return create_app(AgentSettings.from_env(), DockerRuntime())
