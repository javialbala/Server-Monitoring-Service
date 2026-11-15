import io
import sqlite3

import pytest

from minipaas.controlplane import manage
from minipaas.controlplane.config import ConfigError, ControlPlaneSettings

PASSWORD = "contraseña-cli-de-prueba"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "cli" / "x.sqlite3"
    monkeypatch.setenv("MINIPAAS_DB_PATH", str(path))
    return path


def run(monkeypatch, *argv, stdin=""):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return manage.main(list(argv))


def stored_hash(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT password_hash FROM users").fetchone()[0]
    finally:
        conn.close()


def test_create_admin_from_stdin(db_path, monkeypatch, capsys):
    code = run(
        monkeypatch,
        "create-admin",
        "--username",
        "admin",
        "--password-stdin",
        stdin=PASSWORD + "\n",
    )
    out = capsys.readouterr()
    assert code == 0
    assert PASSWORD not in out.out + out.err
    assert stored_hash(db_path).startswith("$argon2id$")


def test_second_create_admin_fails_without_changes(db_path, monkeypatch, capsys):
    args = ("create-admin", "--username", "admin", "--password-stdin")
    run(monkeypatch, *args, stdin=PASSWORD + "\n")
    before = stored_hash(db_path)
    code = run(monkeypatch, *args, stdin="otra-contraseña-distinta\n")
    assert code == 1
    assert "Ya existe un administrador; no se modifica." in capsys.readouterr().err
    assert stored_hash(db_path) == before


def test_weak_password_is_rejected(db_path, monkeypatch, capsys):
    code = run(
        monkeypatch, "create-admin", "--username", "admin", "--password-stdin", stdin="corta\n"
    )
    assert code == 1
    assert "entre 12 y 128" in capsys.readouterr().err


def test_password_is_not_a_command_line_option(db_path, monkeypatch):
    with pytest.raises(SystemExit):
        run(monkeypatch, "create-admin", "--username", "admin", "--password", "secreto-secreto")


def test_interactive_password_must_match(db_path, monkeypatch, capsys):
    answers = iter([PASSWORD, "distinta-de-la-primera"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(answers))
    assert run(monkeypatch, "create-admin", "--username", "admin") == 1
    assert "no coinciden" in capsys.readouterr().err


def test_migrate_and_db_version(db_path, monkeypatch, capsys):
    assert run(monkeypatch, "db-version") == 0
    assert "instalada: 0" in capsys.readouterr().out
    assert run(monkeypatch, "migrate") == 0
    assert "[1, 2]" in capsys.readouterr().out
    assert run(monkeypatch, "migrate") == 0
    assert "ninguna" in capsys.readouterr().out
    assert run(monkeypatch, "db-version") == 0
    assert "instalada: 2. Última disponible: 2" in capsys.readouterr().out


def test_cookie_secure_must_be_boolean(monkeypatch):
    monkeypatch.setenv("MINIPAAS_AGENT_TOKEN_FILE", "/x")
    monkeypatch.setenv("MINIPAAS_COOKIE_SECURE", "quizá")
    with pytest.raises(ConfigError, match="MINIPAAS_COOKIE_SECURE"):
        ControlPlaneSettings.from_env()
