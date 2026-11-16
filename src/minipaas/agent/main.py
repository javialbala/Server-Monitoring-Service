"""API interna del agente: solo rutas GET de lectura, autenticadas con token."""

import hmac
from typing import Annotated

import docker
from fastapi import Depends, FastAPI, Header, HTTPException

from minipaas.agent import containers, host_metrics
from minipaas.agent.config import AgentSettings
from minipaas.common.secrets import read_token

DOCKER_API_VERSION = "1.44"  # Docker Engine 25 o superior


def create_app(settings: AgentSettings, client: docker.DockerClient) -> FastAPI:
    token = read_token(settings.token_file)  # falla al arrancar si el token no es válido

    def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = f"Bearer {token}"
        # compare_digest evita filtrar información por el tiempo de comparación.
        # Mismo error si falta o no coincide: no se revela cuál.
        if authorization is None or not hmac.compare_digest(
            authorization.encode(), expected.encode()
        ):
            raise HTTPException(status_code=401, detail="No autorizado")

    # Sin documentación OpenAPI: el agente no tiene por qué exponerla.
    # El token se exige en todas las rutas a la vez.
    app = FastAPI(
        title="MiniPaaS agent",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(require_token)],
    )

    # Las funciones son "def" (no "async"): FastAPI las ejecuta en un hilo y
    # la espera de 0,5 s para medir la CPU no bloquea el resto.
    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "docker": containers.docker_status(client)}

    @app.get("/metrics")
    def metrics() -> dict:
        return host_metrics.collect_metrics(hostfs=settings.hostfs)

    @app.get("/containers")
    def list_containers() -> dict:
        try:
            running = containers.list_running_containers(client)
        except Exception:  # noqa: BLE001 - no se filtran detalles internos de Docker
            raise HTTPException(status_code=503, detail="Docker no está disponible") from None
        return {"collected_at": host_metrics.now_iso(), "containers": running}

    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`: solo aquí se exige el entorno real."""
    # Con versión fija el cliente no consulta al daemon al crearse: así el agente arranca
    # aunque Docker no esté disponible (/health lo mostrará) y se recupera solo después.
    return create_app(AgentSettings.from_env(), docker.from_env(version=DOCKER_API_VERSION))
