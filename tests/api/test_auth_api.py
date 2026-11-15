import pytest
from conftest import PASSWORD, USERNAME, make_app, make_settings
from fastapi.testclient import TestClient

from minipaas.controlplane.security.passwords import WeakPassword
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.services.auth import AdminAlreadyExists, InvalidUsername

LOGIN = "/api/auth/login"
BAD_CREDENTIALS = {"detail": "Usuario o contraseña incorrectos"}


def login(client, username=USERNAME, password=PASSWORD, **kwargs):
    return client.post(LOGIN, json={"username": username, "password": password}, **kwargs)


def test_session_status_without_admin(client):
    body = client.get("/api/auth/session").json()
    assert body == {
        "authenticated": False,
        "setup_required": True,
        "user": None,
        "csrf_token": None,
    }


def test_session_status_with_admin_not_logged_in(client, admin):
    body = client.get("/api/auth/session").json()
    assert body["setup_required"] is False and body["authenticated"] is False


def test_login_ok_and_cookie_flags(client, admin):
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {"username": USERNAME} and len(body["csrf_token"]) >= 43
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("minipaas_session=")
    for part in ("HttpOnly", "SameSite=strict", "Path=/", "Max-Age=28800"):
        assert part.lower() in cookie.lower()
    assert "secure" not in cookie.lower()


def test_cookie_is_secure_when_configured(tmp_path, clock):
    app = make_app(make_settings(tmp_path, cookie_secure=True), clock)
    with TestClient(app) as client:
        app.state.auth.create_admin(app.state.db.connect(), USERNAME, PASSWORD, "test")
        assert "secure" in login(client).headers["set-cookie"].lower()


def test_session_status_when_logged_in(logged_in):
    body = logged_in.client.get("/api/auth/session").json()
    assert body["authenticated"] is True and body["csrf_token"] == logged_in.csrf
    assert body["user"] == {"username": USERNAME}


def test_me(logged_in):
    body = logged_in.client.get("/api/auth/me").json()
    assert body["username"] == USERNAME and "created_at" in body


def test_wrong_password_and_unknown_user_look_identical(client, admin):
    wrong = login(client, password="contraseña-incorrecta")
    unknown = login(client, username="no-existe")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == BAD_CREDENTIALS
    assert "set-cookie" not in wrong.headers and "set-cookie" not in unknown.headers


def test_username_is_case_insensitive(client, admin):
    assert login(client, username="ADMIN").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"username": "a"},
        {"username": "", "password": "x"},
        {"username": "a", "password": ""},
        {"username": "a", "password": "x" * 129},
        {"username": "a", "password": "x", "extra": 1},
    ],
)
def test_login_validation(client, body):
    assert client.post(LOGIN, json=body).status_code == 422


def test_private_routes_require_session(client):
    for method, url in [
        ("get", "/api/auth/me"),
        ("get", "/api/applications"),
        ("post", "/api/auth/logout"),
        ("get", "/api/applications/x"),
        ("delete", "/api/applications/x"),
    ]:
        response = getattr(client, method)(url)
        assert response.status_code == 401, url
        assert response.json() == {"detail": "Sesión no iniciada o caducada"}


def test_invalid_cookie_is_cleared(client):
    client.cookies.set("minipaas_session", "inventada")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert (
        'minipaas_session=""' in response.headers["set-cookie"]
        or "Max-Age=0" in response.headers["set-cookie"]
    )


def test_logout_revokes_session_and_clears_cookie(logged_in):
    client = logged_in.client
    response = client.post("/api/auth/logout", headers=logged_in.headers)
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    client.cookies.set("minipaas_session", logged_in.cookie)  # reutiliza la cookie antigua
    assert client.get("/api/auth/me").status_code == 401


def test_revoked_session_is_rejected(logged_in, app):
    conn = app.state.db.connect()
    conn.execute("UPDATE sessions SET revoked_at = '2030-01-01T12:00:00+00:00'")
    conn.close()
    assert logged_in.client.get("/api/auth/me").status_code == 401


def test_absolute_expiry(logged_in, clock):
    for _ in range(16):
        clock.advance(minutes=29)
        assert logged_in.client.get("/api/auth/me").status_code == 200
    clock.advance(minutes=29)
    assert logged_in.client.get("/api/auth/me").status_code == 401


def test_idle_expiry(logged_in, clock):
    clock.advance(minutes=31)
    assert logged_in.client.get("/api/auth/me").status_code == 401


def test_activity_keeps_session_alive(logged_in, clock):
    for _ in range(5):
        clock.advance(minutes=20)
        assert logged_in.client.get("/api/auth/me").status_code == 200


def test_sixth_failed_attempt_is_blocked_even_with_right_password(client, admin):
    for _ in range(5):
        assert login(client, password="mala-contraseña-12345").status_code == 401
    blocked = login(client, password="mala-contraseña-12345")
    assert blocked.status_code == 429
    assert blocked.json() == {
        "detail": "Demasiados intentos fallidos. Inténtalo de nuevo más tarde."
    }
    assert int(blocked.headers["retry-after"]) > 0
    assert login(client).status_code == 429  # ni la contraseña correcta mientras dure


def test_unblocked_after_window(client, admin, clock):
    for _ in range(5):
        login(client, password="mala-contraseña-12345")
    clock.advance(minutes=15, seconds=1)
    assert login(client).status_code == 200


def test_injected_rate_limiter_is_used(tmp_path, clock):
    limiter = LoginRateLimiter(max_failures=1, window_minutes=1, clock=clock)
    with TestClient(make_app(make_settings(tmp_path), clock, limiter)) as client:
        assert login(client).status_code == 401
        assert login(client).status_code == 429


def test_login_renews_session_identifier(client, admin):
    first = login(client)
    first_cookie = client.cookies["minipaas_session"]
    second = login(client)  # el cliente envía la cookie anterior
    second_cookie = client.cookies["minipaas_session"]
    assert first_cookie != second_cookie
    assert first.json()["csrf_token"] != second.json()["csrf_token"]
    client.cookies.set("minipaas_session", first_cookie)
    assert client.get("/api/auth/me").status_code == 401  # la primera quedó revocada


def test_database_stores_hashes_not_secrets(logged_in, query, app):
    rows = query("SELECT * FROM sessions")
    assert len(rows) == 1 and rows[0]["token_hash"] != logged_in.cookie
    dump = repr(query("SELECT * FROM users") + rows)
    assert logged_in.cookie not in dump and PASSWORD not in dump
    assert query("SELECT password_hash FROM users")[0]["password_hash"].startswith("$argon2id$")


def test_create_admin_twice_fails(app, admin):
    conn = app.state.db.connect()
    with pytest.raises(AdminAlreadyExists):
        app.state.auth.create_admin(conn, "otro-admin", PASSWORD, "test")
    conn.close()


def test_create_admin_validates_input(app, client):
    conn = app.state.db.connect()
    with pytest.raises(WeakPassword):
        app.state.auth.create_admin(conn, "admin", "corta", "test")
    with pytest.raises(InvalidUsername):
        app.state.auth.create_admin(conn, "ab", PASSWORD, "test")
    conn.close()
    assert client.get("/api/auth/session").json()["setup_required"] is True


def test_login_rehashes_weak_hashes(app, client, query):
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    conn = app.state.db.connect()
    conn.execute(
        "INSERT INTO users (username, password_hash, created_at, updated_at)"
        " VALUES ('admin', ?, 'x', 'x')",
        (weak,),
    )
    conn.close()
    assert login(client).status_code == 200
    assert query("SELECT password_hash FROM users")[0]["password_hash"] != weak
