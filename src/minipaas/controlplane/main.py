"""API del control plane y servidor del panel web (sin privilegios, sin acceso a Docker)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from minipaas.common.secrets import read_token
from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.api import applications, auth, health
from minipaas.controlplane.clock import Clock, utc_now
from minipaas.controlplane.config import ControlPlaneSettings
from minipaas.controlplane.db.connection import Database, transaction
from minipaas.controlplane.security.csrf import check_origin
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.security.sessions import SessionService
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.applications import ApplicationService
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.auth import AuthService

WEB_DIR = Path(__file__).parent / "web"

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
    clock: Clock | None = None,
    rate_limiter: LoginRateLimiter | None = None,
) -> FastAPI:
    clock = clock or utc_now
    db = Database(settings.db_path)
    audit_service = AuditService(clock)
    sessions = SessionService(settings.session_idle_minutes, settings.session_absolute_hours, clock)
    limiter = rate_limiter or LoginRateLimiter(
        settings.login_max_failures, settings.login_window_minutes, clock
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Las migraciones se aplican ANTES de aceptar peticiones.
        applied = db.initialize()
        if applied:
            conn = db.connect()
            try:
                with transaction(conn):
                    audit_service.record(
                        conn,
                        audit.DATABASE_MIGRATE,
                        audit.SUCCESS,
                        metadata={"versions": ",".join(map(str, applied)), "source": "startup"},
                    )
            finally:
                conn.close()
        yield
        await agent_client.aclose()  # cierra las conexiones HTTP al apagar

    # check_origin se aplica a todas las rutas de la API (solo actúa en métodos no seguros).
    # Sin /docs ni /redoc: esas páginas cargan Swagger/ReDoc desde un CDN (prohibido en el
    # proyecto y bloqueado por la CSP). Se mantiene /openapi.json, que es un JSON local.
    app = FastAPI(
        title="MiniPaaS control plane",
        lifespan=lifespan,
        dependencies=[Depends(check_origin)],
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.agent_client = agent_client
    app.state.sessions = sessions
    app.state.auth = AuthService(sessions, audit_service, limiter, clock)
    app.state.applications = ApplicationService(audit_service, clock)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"  # datos privados: que nada los cachee
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(applications.router)

    # Debe montarse al final: si no, taparía las rutas /api.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`."""
    settings = ControlPlaneSettings.from_env()
    token = read_token(settings.token_file)
    client = AgentClient(settings.agent_url, token, settings.agent_timeout)
    return create_app(settings, client)
