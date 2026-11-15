"""API del control plane y servidor del panel web (sin privilegios, sin acceso a Docker)."""

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from minipaas.common.secrets import read_token
from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.agent_runtime_client import AgentRuntimeClient
from minipaas.controlplane.api import applications, auth, catalog, deployments, health, services
from minipaas.controlplane.clock import Clock, utc_now
from minipaas.controlplane.config import ControlPlaneSettings
from minipaas.controlplane.db.connection import Database, transaction
from minipaas.controlplane.security.csrf import check_origin
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.security.sessions import SessionService
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.app_lifecycle import AppLifecycle
from minipaas.controlplane.services.app_services import AppServices
from minipaas.controlplane.services.applications import ApplicationService
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.auth import AuthService
from minipaas.controlplane.services.deploy_engine import AppLocks, DeployEngine
from minipaas.controlplane.services.deployments import Deployments
from minipaas.controlplane.services.errors import ServiceError

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
    runtime_client: AgentRuntimeClient,
    clock: Clock | None = None,
    rate_limiter: LoginRateLimiter | None = None,
    executor: Executor | None = None,
    sleep: Callable[[float], None] | None = None,
) -> FastAPI:
    """`runtime_client` es el cliente síncrono que usa el motor; `executor` y `sleep` son
    inyectables para que los tests no esperen de verdad (por defecto, 2 hilos de trabajo)."""
    clock = clock or utc_now
    # Al apagar se activa este evento: las esperas reales del motor (`stopping.wait`) se
    # interrumpen al momento y la operación en curso se abandona sin juzgarla (ADR-034).
    stopping = threading.Event()
    sleep = sleep or stopping.wait
    executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="minipaas-worker")
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
        lifecycle.interrupt_pending()  # operaciones que quedaron a medias en un reinicio
        yield
        # Orden importante: primero se avisa al motor y se espera a que suelte la operación;
        # solo después se cierran los clientes (si no, sus errores parecerían fallos reales).
        engine.request_stop()
        await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)
        runtime_client.close()
        await agent_client.aclose()  # cierra las conexiones HTTP al apagar

    include_test = settings.enable_test_catalog
    locks = AppLocks()
    engine = DeployEngine(
        db, runtime_client, audit_service, locks, clock, include_test, sleep, stopping
    )
    applications_service = ApplicationService(audit_service, clock)
    lifecycle = AppLifecycle(
        db,
        runtime_client,
        engine,
        applications_service,
        audit_service,
        locks,
        lambda slug: executor.submit(lifecycle.recover_quietly, slug),
        clock,
    )

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
    app.state.applications = applications_service
    app.state.app_services = AppServices(audit_service, include_test, clock)
    app.state.deployments = Deployments(
        audit_service, include_test, lambda *args: executor.submit(engine.run, *args), clock
    )
    app.state.lifecycle = lifecycle
    app.state.executor = executor
    app.state.engine = engine

    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse({"detail": error.message}, status_code=error.status_code)

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
    app.include_router(catalog.router)
    app.include_router(services.router)
    app.include_router(deployments.router)

    # Debe montarse al final: si no, taparía las rutas /api.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def build_app_from_env() -> FastAPI:
    """Factoría para `uvicorn --factory`."""
    settings = ControlPlaneSettings.from_env()
    token = read_token(settings.token_file)
    client = AgentClient(settings.agent_url, token, settings.agent_timeout)
    runtime_client = AgentRuntimeClient(settings.agent_url, token)
    return create_app(settings, client, runtime_client=runtime_client)
