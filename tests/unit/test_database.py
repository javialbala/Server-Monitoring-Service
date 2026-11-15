import sqlite3

import pytest

from minipaas.controlplane.db import migrations
from minipaas.controlplane.db.connection import Database, transaction

NOW = "2030-01-01T00:00:00+00:00"


def insert_user(conn, name="alice"):
    return conn.execute(
        "INSERT INTO users (username, password_hash, created_at, updated_at) VALUES (?,?,?,?)",
        (name, "hash", NOW, NOW),
    ).lastrowid


def insert_session(conn, user_id, digest="h1"):
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, last_seen_at,"
        " expires_at) VALUES (?,?,?,?,?,?)",
        (digest, user_id, "csrf", NOW, NOW, NOW),
    )


def test_creates_directory_and_file(tmp_path):
    db = Database(tmp_path / "nuevo" / "dir" / "x.sqlite3")
    assert db.initialize() == [1]
    assert (tmp_path / "nuevo" / "dir" / "x.sqlite3").exists()


def test_initialize_is_idempotent(tmp_path):
    db = Database(tmp_path / "x.sqlite3")
    assert db.initialize() == [1]
    assert db.initialize() == []
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
    assert migrations.current_version(conn) == 1


def test_wal_and_pragmas(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_deleting_user_deletes_sessions(conn):
    user_id = insert_user(conn)
    insert_session(conn, user_id)
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_session_with_unknown_user_fails(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_session(conn, 999)


@pytest.mark.parametrize("username", ["ab", "x" * 65])
def test_username_length_check(conn, username):
    with pytest.raises(sqlite3.IntegrityError):
        insert_user(conn, username)


def test_username_is_case_insensitive_unique(conn):
    insert_user(conn, "Admin")
    with pytest.raises(sqlite3.IntegrityError):
        insert_user(conn, "admin")


def insert_app(conn, slug="mi-app", name="Mi app", description="", status="draft"):
    conn.execute(
        "INSERT INTO applications (slug, name, description, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?)",
        (slug, name, description, status, NOW, NOW),
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slug": "ab"},
        {"slug": "x" * 41},
        {"name": ""},
        {"name": "n" * 101},
        {"description": "d" * 501},
        {"status": "inexistente"},
    ],
)
def test_application_checks(conn, kwargs):
    with pytest.raises(sqlite3.IntegrityError):
        insert_app(conn, **kwargs)


def test_audit_outcome_check(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO audit_events (occurred_at, event_type, outcome) VALUES (?,?,?)",
            (NOW, "x", "quizá"),
        )


def test_transaction_commits(conn):
    with transaction(conn):
        insert_user(conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_transaction_rolls_back_on_exception(conn):
    with pytest.raises(RuntimeError), transaction(conn):
        insert_user(conn)
        raise RuntimeError("fallo")
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert not conn.in_transaction


def test_user_data_survives_new_connection(tmp_path):
    db = Database(tmp_path / "x.sqlite3")
    db.initialize()
    first = db.connect()
    insert_user(first)
    first.close()
    second = Database(tmp_path / "x.sqlite3").connect()
    assert second.execute("SELECT username FROM users").fetchone()[0] == "alice"
