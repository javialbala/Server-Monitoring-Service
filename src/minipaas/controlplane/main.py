"""API del control plane y servidor del panel web (sin privilegios, sin acceso a Docker)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from minipaas.common.secrets import read_token
from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.config import ControlPlaneSettings

WEB_DIR = Path(__file__).parent / "web"

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def create_app(agent_client: AgentClient) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await agent_client.aclose()  # cierra las conexiones HTTP al apagar

    app = FastAPI(title="MiniPaaS control plane", lifespan=lifespan)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.get("/api/health")
    async def health() -> dict:
        # Información mínima: sin versiones ni motivos técnicos. Siempre 200;
        # el panel interpreta el campo "status".
        agent = await agent_client.health()
        healthy = agent.reachable and agent.docker_reachable
        return {
            "status": "ok" if healthy else "degraded",
            "agent": {"reachable": agent.reachable},
            "docker": {"reachable": agent.docker_reachable},
        }

    # Debe montarse al final: si no, taparía las rutas /api.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`."""
    settings = ControlPlaneSettings.from_env()
    token = read_token(settings.token_file)
    client = AgentClient(settings.agent_url, token, settings.agent_timeout)
    return create_app(client)
