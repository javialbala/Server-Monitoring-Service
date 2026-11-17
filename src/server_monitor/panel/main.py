import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from server_monitor.panel.agent_client import AgentClient
from server_monitor.panel.config import PanelSettings
from server_monitor.panel.routes import router
from server_monitor.panel.security.csrf import check_origin
from server_monitor.panel.security.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    hash_password,
    is_valid_password,
)
from server_monitor.panel.security.rate_limit import LoginRateLimiter
from server_monitor.panel.security.sessions import SessionStore

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def create_app(
    settings: PanelSettings,
    agent_client: AgentClient,
    password_hash: str,
    *,
    sessions: SessionStore | None = None,
    limiter: LoginRateLimiter | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await agent_client.aclose()

    # Sin /docs ni /redoc: cargan Swagger/ReDoc desde un CDN que la CSP bloquea.
    app = FastAPI(
        title="Server Monitoring Service panel",
        lifespan=lifespan,
        dependencies=[Depends(check_origin)],
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.agent_client = agent_client
    app.state.password_hash = password_hash
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
            response.headers["Cache-Control"] = "no-store"
        else:
            # Los estáticos se revalidan siempre: evita servir JS antiguo tras actualizar.
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(router)

    # Debe montarse al final: si no, taparía las rutas /api.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def build_app_from_env() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    password = os.environ.get("APP_PASSWORD", "")
    if not is_valid_password(password):
        logger.error(
            "APP_PASSWORD falta, está vacía o no tiene entre %d y %d caracteres: "
            "escríbela en el servicio panel de docker-compose.yml y ejecuta docker compose up -d",
            MIN_PASSWORD_LENGTH,
            MAX_PASSWORD_LENGTH,
        )
        raise SystemExit(1)
    settings = PanelSettings.from_env()
    client = AgentClient(settings.agent_url, settings.agent_timeout)
    return create_app(settings, client, hash_password(password))
