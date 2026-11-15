import pytest

BASE = "/api/applications"
FIELDS = {"slug", "name", "description", "status", "status_label", "created_at", "updated_at"}


def create(logged_in, **body):
    return logged_in.client.post(BASE, json=body, headers=logged_in.headers)


def test_create_valid(logged_in):
    response = create(logged_in, name="Mi App", slug="mi-app", description="  Demo ")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == FIELDS  # sin id interno
    assert body["slug"] == "mi-app" and body["description"] == "Demo"
    assert body["status"] == "draft" and body["status_label"] == "Sin desplegar"


def test_slug_is_derived_from_name_without_accents(logged_in):
    body = create(logged_in, name="Aplicación Número Uno").json()
    assert body["slug"] == "aplicacion-numero-uno"


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x", "slug": ""},
        {"name": "x", "slug": "MAYUS"},
        {"name": "x", "slug": "dos--guiones"},
        {"name": "x", "slug": "ab"},
        {"name": "x", "slug": "a" * 41},
        {"name": "x", "slug": "con espacio"},
        {"name": "x", "slug": "-empieza"},
        {"name": ""},
        {"name": "   "},
        {"name": "n" * 101},
        {"name": "x", "description": "d" * 501},
        {"name": "x", "extra": 1},
        {},
    ],
)
def test_invalid_input_is_422(logged_in, body):
    assert create(logged_in, **body).status_code == 422


def test_underivable_slug_is_422_with_clear_message(logged_in):
    response = create(logged_in, name="???")
    assert response.status_code == 422
    assert "identificador" in response.json()["detail"]


def test_duplicate_is_409_and_leaves_no_trace(logged_in, query):
    create(logged_in, name="A", slug="repetida")
    response = create(logged_in, name="B", slug="repetida")
    assert response.status_code == 409
    assert response.json() == {"detail": "Ya existe una aplicación con ese identificador"}
    assert query("SELECT name FROM applications") == [{"name": "A"}]
    events = query("SELECT outcome FROM audit_events WHERE event_type = 'application.create'")
    assert sorted(e["outcome"] for e in events) == ["failure", "success"]  # solo 1 éxito: el de A


def test_list_is_ordered_newest_first(logged_in, clock):
    create(logged_in, name="Primera")
    clock.advance(minutes=1)
    create(logged_in, name="Segunda")
    items = logged_in.client.get(BASE).json()["items"]
    assert [i["slug"] for i in items] == ["segunda", "primera"]


def test_get_and_404(logged_in):
    create(logged_in, name="Existe")
    assert logged_in.client.get(f"{BASE}/existe").json()["name"] == "Existe"
    response = logged_in.client.get(f"{BASE}/nada")
    assert response.status_code == 404 and response.json() == {"detail": "Aplicación no encontrada"}


def test_patch(logged_in, clock):
    create(logged_in, name="Vieja", slug="app-uno")
    clock.advance(minutes=5)
    response = logged_in.client.patch(
        f"{BASE}/app-uno", json={"name": "Nueva", "description": "Texto"}, headers=logged_in.headers
    )
    body = response.json()
    assert response.status_code == 200
    assert (body["name"], body["description"], body["slug"]) == ("Nueva", "Texto", "app-uno")
    assert body["updated_at"] != body["created_at"]


def test_patch_partial(logged_in):
    create(logged_in, name="Vieja", slug="app-uno", description="d")
    body = logged_in.client.patch(
        f"{BASE}/app-uno", json={"name": "N"}, headers=logged_in.headers
    ).json()
    assert (body["name"], body["description"]) == ("N", "d")


@pytest.mark.parametrize(
    "body", [{"slug": "otro-slug"}, {}, {"name": "x", "slug": "otro"}, {"name": ""}]
)
def test_patch_invalid_is_422(logged_in, body):
    create(logged_in, name="Vieja", slug="app-uno")
    response = logged_in.client.patch(f"{BASE}/app-uno", json=body, headers=logged_in.headers)
    assert response.status_code == 422


def test_patch_unknown_is_404(logged_in):
    response = logged_in.client.patch(f"{BASE}/nada", json={"name": "x"}, headers=logged_in.headers)
    assert response.status_code == 404


def test_patch_without_changes_writes_no_event(logged_in, query):
    create(logged_in, name="Igual", slug="app-uno")
    before = query("SELECT COUNT(*) AS n FROM audit_events")[0]["n"]
    logged_in.client.patch(f"{BASE}/app-uno", json={"name": "Igual"}, headers=logged_in.headers)
    assert query("SELECT COUNT(*) AS n FROM audit_events")[0]["n"] == before


def test_delete_then_404(logged_in):
    create(logged_in, name="Borrar", slug="app-uno")
    assert logged_in.client.delete(f"{BASE}/app-uno", headers=logged_in.headers).status_code == 204
    assert logged_in.client.get(f"{BASE}/app-uno").status_code == 404
    assert logged_in.client.delete(f"{BASE}/app-uno", headers=logged_in.headers).status_code == 404
    assert logged_in.client.get(BASE).json() == {"items": []}
