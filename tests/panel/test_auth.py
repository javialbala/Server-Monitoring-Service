import pytest
from conftest import PASSWORD

from minipaas.controlplane import manage
from minipaas.controlplane.security.passwords import hash_password, verify_password
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.security.sessions import SessionStore


def test_login_ok_sets_cookie_with_secure_flags(client):
    response = client.post("/api/login", json={"password": PASSWORD})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "minipaas_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "secure" not in cookie  # cookie_secure es false por defecto
    session = client.get("/api/session").json()
    assert session["authenticated"] is True
    assert session["csrf_token"]


def test_login_wrong_password(client):
    response = client.post("/api/login", json={"password": "incorrecta"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Contraseña incorrecta"}
    assert client.get("/api/session").json() == {"authenticated": False, "csrf_token": None}


def test_login_without_password_configured_is_503(client, hash_file):
    hash_file.unlink()
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 503


def test_blocked_after_too_many_failures(client):
    for _ in range(5):
        assert client.post("/api/login", json={"password": "mal"}).status_code == 401
    response = client.post("/api/login", json={"password": PASSWORD})  # ni la correcta pasa
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_logout_requires_csrf(client, csrf):
    assert client.post("/api/logout").status_code == 403
    assert client.get("/api/session").json()["authenticated"] is True  # sigue la sesión
    assert client.post("/api/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/session").json()["authenticated"] is False


def test_logout_without_session_is_401(client):
    assert client.post("/api/logout").status_code == 401


def test_cross_origin_post_is_rejected(client):
    response = client.post(
        "/api/login", json={"password": PASSWORD}, headers={"Origin": "http://evil.example"}
    )
    assert response.status_code == 403


def test_session_expires_by_inactivity_and_by_age():
    now = [0.0]
    store = SessionStore(idle_minutes=30, absolute_hours=8, clock=lambda: now[0])
    token, _ = store.create()
    now[0] = 29 * 60
    assert store.get(token) is not None  # renueva la inactividad
    now[0] += 31 * 60
    assert store.get(token) is None  # inactiva más de 30 min

    token, _ = store.create()
    for _ in range(17):  # activa cada 29 min, pero a las 8 h caduca igualmente
        now[0] += 29 * 60
        store.get(token)
    assert store.get(token) is None


def test_rate_limiter_window():
    now = [0.0]
    limiter = LoginRateLimiter(max_failures=2, window_minutes=1, clock=lambda: now[0])
    limiter.record_failure("1.1.1.1")
    assert limiter.is_blocked("1.1.1.1") is None
    limiter.record_failure("1.1.1.1")
    assert limiter.is_blocked("1.1.1.1") == 60
    assert limiter.is_blocked("2.2.2.2") is None  # solo afecta a esa IP
    now[0] = 61
    assert limiter.is_blocked("1.1.1.1") is None


# --- set-password ---


def test_set_password_stores_hash_not_plaintext(tmp_path, monkeypatch, capsys):
    path = tmp_path / "datos" / "password_hash"
    monkeypatch.setenv("MINIPAAS_PASSWORD_HASH_FILE", str(path))
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("mi-clave\n"))
    assert manage.main(["set-password", "--stdin"]) == 0
    content = path.read_text()
    assert "mi-clave" not in content
    assert content.startswith("$argon2id$")
    assert verify_password(content.strip(), "mi-clave")
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("password", ["abc", "x" * 129])
def test_set_password_rejects_bad_length(tmp_path, monkeypatch, password):
    path = tmp_path / "password_hash"
    monkeypatch.setenv("MINIPAAS_PASSWORD_HASH_FILE", str(path))
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(password + "\n"))
    assert manage.main(["set-password", "--stdin"]) == 1
    assert not path.exists()


def test_set_password_accepts_4_characters_and_replaces_old_hash(tmp_path, monkeypatch):
    path = tmp_path / "password_hash"
    path.write_text(hash_password("antigua"))
    monkeypatch.setenv("MINIPAAS_PASSWORD_HASH_FILE", str(path))
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("abcd\n"))
    assert manage.main(["set-password", "--stdin"]) == 0
    assert verify_password(path.read_text().strip(), "abcd")
