import sqlite3

import pytest

from minipaas.controlplane.db import migrations
from minipaas.controlplane.db.connection import Database
from minipaas.controlplane.db.migrations import MigrationError


def write(directory, name, sql):
    directory.mkdir(exist_ok=True)
    (directory / name).write_text(sql, encoding="utf-8")


def test_available_migrations_are_ordered():
    found = migrations.available_migrations()
    assert [m.version for m in found] == sorted(m.version for m in found)
    assert found[0].name == "initial"


def test_current_version_is_zero_on_empty_database(tmp_path):
    conn = Database(tmp_path / "x.sqlite3").connect()
    assert migrations.current_version(conn) == 0


def test_newer_database_is_rejected(tmp_path):
    db = Database(tmp_path / "x.sqlite3")
    db.initialize()
    conn = db.connect()
    conn.execute("INSERT INTO schema_migrations VALUES (99, 'futura', 'ahora')")
    conn.close()
    with pytest.raises(MigrationError, match="más nueva que el código"):
        db.initialize()


def test_badly_named_file_is_rejected(tmp_path):
    write(tmp_path / "m", "inicial.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="inválido"):
        migrations.available_migrations(tmp_path / "m")


def test_duplicate_versions_are_rejected(tmp_path):
    write(tmp_path / "m", "0001_a.sql", "SELECT 1;")
    write(tmp_path / "m", "0001_b.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="duplicada"):
        migrations.available_migrations(tmp_path / "m")


def test_failing_migration_leaves_no_partial_changes(tmp_path):
    directory = tmp_path / "m"
    write(
        directory, "0001_rota.sql", "CREATE TABLE a (x INTEGER);\nINSERT INTO no_existe VALUES (1);"
    )
    db = Database(tmp_path / "x.sqlite3", directory)
    with pytest.raises(sqlite3.OperationalError):
        db.initialize()
    conn = db.connect()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" not in tables
    assert migrations.current_version(conn) == 0


def test_migrations_apply_in_order_and_only_once(tmp_path):
    directory = tmp_path / "m"
    write(directory, "0001_a.sql", "CREATE TABLE a (x INTEGER);")
    write(
        directory,
        "0002_b.sql",
        "-- comentario\nCREATE TABLE b (x INTEGER);\nINSERT INTO b VALUES (1);",
    )
    db = Database(tmp_path / "x.sqlite3", directory)
    assert db.initialize() == [1, 2]
    write(directory, "0003_c.sql", "CREATE TABLE c (x INTEGER);")
    assert db.initialize() == [3]


def test_incomplete_statement_is_an_error(tmp_path):
    directory = tmp_path / "m"
    write(directory, "0001_a.sql", "CREATE TABLE a (x INTEGER)")
    with pytest.raises(MigrationError, match="incompleta"):
        Database(tmp_path / "x.sqlite3", directory).initialize()


def test_split_statements_keeps_semicolons_inside_strings():
    sql = "INSERT INTO t VALUES ('a;b');\nSELECT 2;"
    assert migrations.split_statements(sql) == ["INSERT INTO t VALUES ('a;b');", "SELECT 2;"]
