"""Fixtures compartidas. Cada test usa su propia base de datos en `tmp_path`."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from minipaas.controlplane.agent_client import AgentClient
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


def make_app(settings, clock=None, rate_limiter=None):
    agent = AgentClient("http://agent:8001", "t" * 40, transport=httpx.MockTransport(agent_ok))
    return create_app(settings, agent, clock=clock, rate_limiter=rate_limiter)


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
def app(settings, clock):
    return make_app(settings, clock)


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
