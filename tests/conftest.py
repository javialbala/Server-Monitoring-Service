"""Fixtures compartidas. Cada test usa su propia base de datos en `tmp_path`."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fakes.fake_agent import TOKEN, FakeAgent
from fastapi.testclient import TestClient

from minipaas.controlplane.agent_client import AgentClient
from minipaas.controlplane.agent_runtime_client import AgentRuntimeClient
from minipaas.controlplane.config import ControlPlaneSettings
from minipaas.controlplane.db.connection import Database
from minipaas.controlplane.main import create_app

PASSWORD = "contraseña-de-prueba-123"
USERNAME = "admin"


class FakeClock:
    """Reloj que solo avanza cuando el test lo pide."""

    def __init__(self) -> None:
        self.now = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def agent_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"status": "ok", "docker": {"reachable": True}})


def make_settings(tmp_path, **overrides) -> ControlPlaneSettings:
    return ControlPlaneSettings(
        agent_url="http://agent:8001",
        token_file="/no/se/usa",
        db_path=str(tmp_path / "data" / "test.sqlite3"),
        **overrides,
    )


class InlineExecutor:
    """Ejecuta el trabajo en el mismo hilo que lo encola: los tests no tienen que esperar."""

    def submit(self, fn, /, *args, **kwargs) -> None:
        fn(*args, **kwargs)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        pass


def make_app(settings, clock=None, rate_limiter=None, fake=None, executor=None):
    """App con un agente falso en memoria. Por defecto, el worker es síncrono y `sleep` solo
    adelanta el reloj falso (así el plazo de las comprobaciones de salud se agota sin esperar)."""
    fake = fake or FakeAgent()
    clock = clock or FakeClock()
    transport = httpx.MockTransport(fake.handler)
    agent = AgentClient("http://agent:8001", TOKEN, transport=transport)
    runtime = AgentRuntimeClient("http://agent:8001", TOKEN, transport=transport)
    app = create_app(
        settings,
        agent,
        runtime_client=runtime,
        clock=clock,
        rate_limiter=rate_limiter,
        executor=executor or InlineExecutor(),
        sleep=lambda seconds: clock.advance(seconds=seconds),
    )
    app.state.fake_agent = fake
    return app


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings(tmp_path) -> ControlPlaneSettings:
    return make_settings(tmp_path)


@pytest.fixture
def conn(tmp_path):
    """Conexión a una base de datos nueva y migrada (para tests unitarios)."""
    db = Database(tmp_path / "unit.sqlite3")
    db.initialize()
    connection = db.connect()
    yield connection
    connection.close()


@pytest.fixture
def fake_agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def app(settings, clock, fake_agent):
    return make_app(settings, clock, fake=fake_agent)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:  # el bloque with ejecuta el arranque (migraciones)
        yield test_client


@pytest.fixture
def query(app):
    """Ejecuta una consulta de solo lectura sobre la base de datos de la app."""

    def run(sql: str, params: tuple = ()) -> list[dict]:
        connection = app.state.db.connect()
        try:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
        finally:
            connection.close()

    return run


@pytest.fixture
def admin(app, client):
    """Crea el administrador por el mismo camino que la CLI."""
    connection = app.state.db.connect()
    try:
        return app.state.auth.create_admin(connection, USERNAME, PASSWORD, source="test")
    finally:
        connection.close()


@dataclass
class LoggedIn:
    client: TestClient
    csrf: str
    cookie: str

    @property
    def headers(self) -> dict:
        return {"X-CSRF-Token": self.csrf}


@pytest.fixture
def logged_in(client, admin) -> LoggedIn:
    response = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    return LoggedIn(client, response.json()["csrf_token"], client.cookies["minipaas_session"])


UNHEALTHY_TIMEOUT = "no respondió a la comprobación de salud"


class Api:
    """Atajos para los tests de la API con sesión iniciada."""

    def __init__(self, logged_in: LoggedIn) -> None:
        self.session = logged_in

    def post(self, path: str, body: dict | None = None):
        return self.session.client.post(path, json=body or {}, headers=self.session.headers)

    def patch(self, path: str, body: dict):
        return self.session.client.patch(path, json=body, headers=self.session.headers)

    def delete(self, path: str):
        return self.session.client.delete(path, headers=self.session.headers)

    def get(self, path: str):
        return self.session.client.get(path)

    def app(self, slug: str = "demo") -> str:
        assert self.post("/api/applications", {"name": slug, "slug": slug}).status_code == 201
        return slug

    def service(self, slug: str, name: str = "web", catalog_id: str = "whoami", **extra):
        body = {"name": name, "catalog_id": catalog_id, **extra}
        response = self.post(f"/api/applications/{slug}/services", body)
        assert response.status_code == 201, response.text
        return response.json()

    def revision(self, slug: str, request_id: str | None = None):
        import uuid

        body = {"request_id": request_id or str(uuid.uuid4())}
        return self.post(f"/api/applications/{slug}/revisions", body)

    def deploy(self, slug: str) -> dict:
        """Crea una revisión y la despliega. Con el worker síncrono devuelve el resultado final."""
        revision = self.revision(slug)
        assert revision.status_code == 201, revision.text
        number = revision.json()["revision"]
        response = self.post(f"/api/applications/{slug}/revisions/{number}/deploy")
        assert response.status_code == 202, response.text
        return self.get(f"/api/applications/{slug}/deployments/{number}").json()

    def application(self, slug: str) -> dict:
        return self.get(f"/api/applications/{slug}").json()


@pytest.fixture
def api(logged_in) -> Api:
    return Api(logged_in)
