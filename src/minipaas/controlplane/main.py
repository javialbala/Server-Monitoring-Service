"""Panel web: API para el navegador y archivos estáticos (sin privilegios, sin acceso a Docker)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from minipaas.common.secrets import read_token
from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.config import ControlPlaneSettings
from minipaas.controlplane.routes import router
from minipaas.controlplane.security.csrf import check_origin
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.security.sessions import SessionStore

WEB_DIR = Path(__file__).parent / "web"

# default-src 'self' prohíbe scripts y estilos en línea y cualquier recurso externo.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def create_app(
    settings: ControlPlaneSettings,
    agent_client: AgentClient,
    *,
    sessions: SessionStore | None = None,
    limiter: LoginRateLimiter | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await agent_client.aclose()  # cierra las conexiones HTTP al apagar

    # check_origin se aplica a todas las rutas de la API (solo actúa en métodos no seguros).
    # Sin /docs ni /redoc: cargan Swagger/ReDoc desde un CDN (bloqueado por la CSP).
    app = FastAPI(
        title="MiniPaaS panel",
        lifespan=lifespan,
        dependencies=[Depends(check_origin)],
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.agent_client = agent_client
    app.state.sessions = sessions or SessionStore(
        settings.session_idle_minutes, settings.session_absolute_hours
    )
    app.state.limiter = limiter or LoginRateLimiter(
        settings.login_max_failures, settings.login_window_minutes
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"  # datos privados: que nada los cachee
        return response

    app.include_router(router)

    # Debe montarse al final: si no, taparía las rutas /api.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`."""
    # Para que se vea el registro de accesos (uvicorn solo configura sus propios loggers).
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = ControlPlaneSettings.from_env()
    token = read_token(settings.token_file)
    client = AgentClient(settings.agent_url, token, settings.agent_timeout)
    return create_app(settings, client)
