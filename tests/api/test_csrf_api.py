import pytest
from conftest import PASSWORD, USERNAME

EVIL = {"Origin": "http://evil.example"}


@pytest.fixture
def app_slug(logged_in):
    logged_in.client.post(
        "/api/applications", json={"name": "Una", "slug": "app-uno"}, headers=logged_in.headers
    )
    return "app-uno"


def requests_for(slug):
    return [
        ("post", "/api/applications", {"name": "Otra"}),
        ("patch", f"/api/applications/{slug}", {"name": "Cambio"}),
        ("delete", f"/api/applications/{slug}", None),
        ("post", "/api/auth/logout", None),
    ]


def send(client, method, url, body, headers):
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(url, **kwargs)


@pytest.mark.parametrize("index", range(4))
def test_correct_token_is_accepted(logged_in, app_slug, index):
    method, url, body = requests_for(app_slug)[index]
    assert send(logged_in.client, method, url, body, logged_in.headers).status_code in (
        200,
        201,
        204,
    )


@pytest.mark.parametrize("index", range(4))
def test_missing_token_is_403(logged_in, app_slug, index):
    method, url, body = requests_for(app_slug)[index]
    response = send(logged_in.client, method, url, body, {})
    assert response.status_code == 403
    assert response.json() == {"detail": "Token CSRF ausente o no válido"}


@pytest.mark.parametrize("index", range(4))
def test_wrong_token_is_403(logged_in, app_slug, index):
    method, url, body = requests_for(app_slug)[index]
    assert send(logged_in.client, method, url, body, {"X-CSRF-Token": "x" * 43}).status_code == 403


def test_token_from_another_session_is_403(logged_in, app, app_slug):
    from fastapi.testclient import TestClient

    with TestClient(app) as other:
        other_csrf = other.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        ).json()["csrf_token"]
    assert other_csrf != logged_in.csrf
    response = logged_in.client.post(
        "/api/applications", json={"name": "X"}, headers={"X-CSRF-Token": other_csrf}
    )
    assert response.status_code == 403


@pytest.mark.parametrize("index", range(4))
def test_foreign_origin_is_403_even_with_valid_token(logged_in, app_slug, index):
    method, url, body = requests_for(app_slug)[index]
    response = send(logged_in.client, method, url, body, {**logged_in.headers, **EVIL})
    assert response.status_code == 403


def test_own_origin_is_accepted(logged_in):
    headers = {**logged_in.headers, "Origin": "http://testserver"}
    assert (
        logged_in.client.post(
            "/api/applications", json={"name": "A1B"}, headers=headers
        ).status_code
        == 201
    )


def test_foreign_origin_on_login_is_403(client, admin):
    response = client.post(
        "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, headers=EVIL
    )
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_get_requests_do_not_change_anything(logged_in, app_slug, query):
    state = (query("SELECT * FROM audit_events"), query("SELECT * FROM applications"))
    for _ in range(3):
        for url in (
            "/api/applications",
            f"/api/applications/{app_slug}",
            "/api/auth/me",
            "/api/auth/session",
        ):
            assert logged_in.client.get(url, headers=EVIL).status_code == 200
    assert (query("SELECT * FROM audit_events"), query("SELECT * FROM applications")) == state


def test_api_responses_are_not_cached(client):
    assert client.get("/api/health").headers["Cache-Control"] == "no-store"
    assert "Cache-Control" not in client.get("/").headers
