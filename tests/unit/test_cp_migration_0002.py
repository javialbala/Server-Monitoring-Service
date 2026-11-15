import shutil
import sqlite3

import pytest

from minipaas.controlplane.db import migrations
from minipaas.controlplane.db.connection import Database

NOW = "2030-01-01T00:00:00+00:00"


def phase2_database(tmp_path) -> Database:
    """Base de datos de la Fase 2: solo la migración 0001, con una aplicación y un usuario."""
    only_first = tmp_path / "m"
    only_first.mkdir()
    shutil.copy(migrations.MIGRATIONS_DIR / "0001_initial.sql", only_first)
    db = Database(tmp_path / "x.sqlite3", only_first)
    assert db.initialize() == [1]
    conn = db.connect()
    conn.execute(
        "INSERT INTO users (username, password_hash, created_at, updated_at)"
        " VALUES ('admin', 'hash', ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO applications (slug, name, created_at, updated_at) VALUES ('vieja', 'V', ?, ?)",
        (NOW, NOW),
    )
    conn.close()
    return Database(tmp_path / "x.sqlite3")  # con todas las migraciones


def test_phase2_data_survives_migration(tmp_path):
    db = phase2_database(tmp_path)
    assert db.initialize() == [2]
    conn = db.connect()
    app = conn.execute("SELECT slug, status, active_deployment_id FROM applications").fetchone()
    assert tuple(app) == ("vieja", "draft", None)
    assert conn.execute("SELECT username FROM users").fetchone()[0] == "admin"
    codes = {r[0] for r in conn.execute("SELECT code FROM application_statuses")}
    assert codes == {"draft", "running", "stopped", "attention"}
    assert conn.execute("SELECT COUNT(*) FROM deployment_statuses").fetchone()[0] == 12


def new_deployment(conn, revision: int, status: str, app_id: int = 1) -> int:
    cursor = conn.execute(
        "INSERT INTO deployments (application_id, revision, operation_id, request_id, status,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (app_id, revision, f"op-{app_id}-{revision}", f"rq-{app_id}-{revision}", status, NOW),
    )
    return cursor.lastrowid


@pytest.fixture
def conn(tmp_path):
    db = phase2_database(tmp_path)
    db.initialize()
    connection = db.connect()
    connection.execute(
        "INSERT INTO applications (slug, name, created_at, updated_at) VALUES ('otra', 'O', ?, ?)",
        (NOW, NOW),
    )
    yield connection
    connection.close()


def test_revision_configuration_is_immutable(conn):
    deployment_id = new_deployment(conn, 1, "healthy")
    conn.execute(
        "INSERT INTO deployment_services (deployment_id, service_name, catalog_id, image_ref,"
        " internal_port, env, memory_mb, cpus) VALUES (?, 'web', 'whoami', 'x@sha256:0', 80, '{}',"
        " 32, 0.25)",
        (deployment_id,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        conn.execute("UPDATE deployment_services SET memory_mb = 64")


@pytest.mark.parametrize("status", ["preparing", "deploying", "rolling_back"])
def test_only_one_operation_in_progress_per_app(conn, status):
    new_deployment(conn, 1, "preparing")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        new_deployment(conn, 2, status)


def test_operations_in_different_apps_or_finished_do_not_collide(conn):
    new_deployment(conn, 1, "preparing")
    new_deployment(conn, 1, "preparing", app_id=2)  # otra aplicación
    new_deployment(conn, 2, "healthy")  # terminada
    new_deployment(conn, 3, "failed")


def test_revision_and_request_are_unique_per_app(conn):
    new_deployment(conn, 1, "pending")
    with pytest.raises(sqlite3.IntegrityError):
        new_deployment(conn, 1, "pending")


def test_host_port_range_and_uniqueness(conn):
    insert = (
        "INSERT INTO services (application_id, name, catalog_id, internal_port, host_port,"
        " memory_mb, cpus, created_at, updated_at) VALUES (1, ?, 'whoami', 80, ?, 32, 0.25, ?, ?)"
    )
    conn.execute(insert, ("web", 20000, NOW, NOW))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("web2", 20000, NOW, NOW))  # puerto repetido
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("web3", 21000, NOW, NOW))  # fuera de rango
