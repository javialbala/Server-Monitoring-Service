"""API interna del agente: mínima y autenticada con token."""

import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from minipaas.agent.config import AgentSettings
from minipaas.agent.docker_runtime import DockerRuntime
from minipaas.common.secrets import read_token


def create_app(settings: AgentSettings, runtime: DockerRuntime) -> FastAPI:
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
    app = FastAPI(title="MiniPaaS agent", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health", dependencies=[Depends(require_token)])
    def health() -> dict:
        status = runtime.ping()
        return {
            "status": "ok",
            "docker": {"reachable": status.reachable, "server_version": status.server_version},
        }

    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`: solo aquí se exige el entorno real."""
    return create_app(AgentSettings.from_env(), DockerRuntime())
