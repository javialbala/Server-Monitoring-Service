import pytest

A = "/api/applications/{}/services"


@pytest.fixture
def slug(api):
    return api.app("demo")


def url(slug, name=""):
    return A.format(slug) + (f"/{name}" if name else "")


def test_create_with_defaults(api, slug):
    response = api.post(url(slug), {"name": "web", "catalog_id": "whoami"})
    assert response.status_code == 201
    assert response.json() == {
        "name": "web", "catalog_id": "whoami", "catalog_name": "Servicio HTTP de prueba (whoami)",
        "internal_port": 80, "publish": False, "host_port": None, "env": {}, "memory_mb": 32,
        "cpus": 0.25, "created_at": response.json()["created_at"],
        "updated_at": response.json()["updated_at"], "protected": False,
    }  # fmt: skip


def test_create_list_get_update_delete(api, slug, query):
    api.service(slug, "web", env={"WHOAMI_NAME": "Hola"}, memory_mb=64)
    assert [s["name"] for s in api.get(url(slug)).json()["items"]] == ["web"]
    response = api.patch(url(slug, "web"), {"memory_mb": 96, "cpus": 0.5})
    assert response.status_code == 200
    assert (response.json()["memory_mb"], response.json()["cpus"]) == (96, 0.5)
    assert response.json()["env"] == {"WHOAMI_NAME": "Hola"}  # sin tocar
    assert api.delete(url(slug, "web")).status_code == 204
    assert api.get(url(slug)).json() == {"items": []}
    events = query(
        "SELECT event_type, resource_id, outcome FROM audit_events"
        " WHERE event_type LIKE 'service.%'"
    )
    assert [(e["event_type"], e["resource_id"], e["outcome"]) for e in events] == [
        ("service.create", "demo/web", "success"),
        ("service.update", "demo/web", "success"),
        ("service.delete", "demo/web", "success"),
    ]


def test_update_audit_has_field_names_never_values(api, slug, query):
    api.service(slug, "web")
    api.patch(url(slug, "web"), {"env": {"WHOAMI_NAME": "valor-privado"}, "memory_mb": 48})
    row = query("SELECT metadata FROM audit_events WHERE event_type = 'service.update'")[0]
    assert row["metadata"] == '{"fields": "env,memory_mb"}'
    assert "valor-privado" not in str(query("SELECT * FROM audit_events"))


def test_patch_without_changes_writes_no_event(api, slug, query):
    api.service(slug, "web")
    assert api.patch(url(slug, "web"), {"memory_mb": 32}).status_code == 200
    assert query("SELECT * FROM audit_events WHERE event_type = 'service.update'") == []


@pytest.mark.parametrize(
    "body",
    [
        {"name": "web", "catalog_id": "no-existe"},
        {"name": "web", "catalog_id": "test-crash"},  # entrada de prueba sin el flag
        {"name": "web", "catalog_id": "whoami", "internal_port": 8080},
        {"name": "web", "catalog_id": "whoami", "env": {"OTRA": "x"}},
        {"name": "web", "catalog_id": "whoami", "env": {"WHOAMI_NAME": "no válido!"}},
        {"name": "web", "catalog_id": "whoami", "env": {"WHOAMI_NAME": "x" * 41}},
        {"name": "web", "catalog_id": "nginx-static", "env": {"WHOAMI_NAME": "x"}},
        {"name": "web", "catalog_id": "whoami", "memory_mb": 1024},
        {"name": "web", "catalog_id": "whoami", "memory_mb": 1},
        {"name": "web", "catalog_id": "whoami", "cpus": 4},
        {"name": "web", "catalog_id": "whoami", "publish": True, "host_port": 19999},
        {"name": "web", "catalog_id": "whoami", "publish": True, "host_port": 21000},
        {"name": "Web", "catalog_id": "whoami"},
        {"name": "w", "catalog_id": "whoami"},
        {"name": "web--x", "catalog_id": "whoami"},
        {"name": "web", "catalog_id": "whoami", "extra": 1},
        {"name": "web", "catalog_id": "whoami", "env": {"WHOAMI_NAME": 5}},
        {"catalog_id": "whoami"},
    ],
)
def test_invalid_data_is_422_and_stores_nothing(api, slug, body):
    assert api.post(url(slug), body).status_code == 422
    assert api.get(url(slug)).json() == {"items": []}


def test_invalid_message_comes_from_catalog(api, slug):
    response = api.post(url(slug), {"name": "web", "catalog_id": "whoami", "memory_mb": 1024})
    assert response.json() == {"detail": "La memoria debe estar entre 16 y 128 MiB."}


def test_duplicate_name_is_409(api, slug):
    api.service(slug, "web")
    response = api.post(url(slug), {"name": "web", "catalog_id": "nginx-static"})
    assert response.status_code == 409


def test_name_and_catalog_are_immutable(api, slug):
    api.service(slug, "web")
    assert api.patch(url(slug, "web"), {"name": "otro"}).status_code == 422
    assert api.patch(url(slug, "web"), {"catalog_id": "nginx-static"}).status_code == 422
    assert api.patch(url(slug, "web"), {}).status_code == 422


def test_isolation_between_applications(api, slug):
    other = api.app("otra")
    api.service(slug, "web")
    api.service(other, "web")  # mismo nombre en otra aplicación: permitido
    api.service(other, "solo-aqui")
    assert [s["name"] for s in api.get(url(slug)).json()["items"]] == ["web"]
    assert api.get(url(slug)).json()["items"][0]["name"] == "web"
    assert api.patch(url(slug, "solo-aqui"), {"memory_mb": 32}).status_code == 404
    assert api.delete(url(slug, "solo-aqui")).status_code == 404


def test_unknown_application_is_404(api):
    assert api.get(url("nada")).status_code == 404
    assert api.post(url("nada"), {"name": "web", "catalog_id": "whoami"}).status_code == 404


# --- Puertos ----------------------------------------------------------------------------


def test_ports_are_assigned_automatically_from_the_lowest(api, slug):
    first = api.service(slug, "uno", publish=True)
    second = api.service(slug, "dos", publish=True)
    api.service(slug, "tres")
    assert (first["host_port"], second["host_port"]) == (20000, 20001)
    assert first["publish"] is True
    assert api.get(url(slug)).json()["items"][2]["host_port"] is None


def test_auto_port_fills_gaps(api, slug):
    api.service(slug, "uno", publish=True)
    api.service(slug, "dos", publish=True, host_port=20005)
    api.delete(url(slug, "uno"))
    assert api.service(slug, "tres", publish=True)["host_port"] == 20000


def test_explicit_port_conflict_with_another_service(api, slug):
    api.service(slug, "uno", publish=True, host_port=20010)
    other = api.app("otra")
    response = api.post(
        url(other), {"name": "ex", "catalog_id": "whoami", "publish": True, "host_port": 20010}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "El puerto 20010 ya está asignado a otro servicio"}


def test_patch_publish_unpublish_and_port(api, slug):
    api.service(slug, "web")
    assert api.patch(url(slug, "web"), {"publish": True}).json()["host_port"] == 20000
    assert api.patch(url(slug, "web"), {"host_port": 20042}).json()["host_port"] == 20042
    assert api.patch(url(slug, "web"), {"memory_mb": 48}).json()["host_port"] == 20042
    body = api.patch(url(slug, "web"), {"publish": False}).json()
    assert (body["publish"], body["host_port"]) == (False, None)


def test_patch_port_conflict_keeps_service_unchanged(api, slug):
    api.service(slug, "uno", publish=True)
    api.service(slug, "dos")
    assert api.patch(url(slug, "dos"), {"host_port": 20000}).status_code == 409
    assert api.get(url(slug)).json()["items"][1]["host_port"] is None


def test_port_of_another_apps_active_revision_is_reserved(api, slug):
    api.service(slug, "web", publish=True)  # 20000
    assert api.deploy(slug)["status"] == "healthy"
    api.post(f"/api/applications/{slug}/stop")  # para poder borrar el servicio
    api.delete(url(slug, "web"))  # la tabla `services` ya no lo usa, la revisión activa sí
    other = api.app("otra")
    response = api.post(
        url(other), {"name": "ex", "catalog_id": "whoami", "publish": True, "host_port": 20000}
    )
    assert response.status_code == 409
    assert api.service(other, "ye", publish=True)["host_port"] == 20001  # salta el reservado


def test_same_app_can_reuse_its_own_active_port(api, slug):
    api.service(slug, "web", publish=True)
    api.deploy(slug)
    api.post(f"/api/applications/{slug}/stop")
    api.delete(url(slug, "web"))
    assert api.service(slug, "nuevo", publish=True)["host_port"] == 20000


def test_no_free_ports_left(api, slug, app):
    conn = app.state.db.connect()
    app_id = conn.execute("SELECT id FROM applications").fetchone()[0]
    conn.executemany(
        "INSERT INTO services (application_id, name, catalog_id, internal_port, host_port,"
        " memory_mb, cpus, created_at, updated_at)"
        " VALUES (?, ?, 'whoami', 80, ?, 32, 0.25, 'x', 'x')",
        [(app_id, f"s{port}", port) for port in range(20000, 21000)],
    )
    conn.close()
    response = api.post(url(slug), {"name": "extra", "catalog_id": "whoami", "publish": True})
    assert response.status_code == 409
    assert response.json() == {"detail": "No quedan puertos libres en el rango 20000–20999"}


def test_failures_are_audited(api, slug, query):
    api.service(slug, "web")
    api.post(url(slug), {"name": "web", "catalog_id": "whoami"})
    rows = query("SELECT outcome, metadata FROM audit_events WHERE event_type = 'service.create'")
    assert sorted(r["outcome"] for r in rows) == ["failure", "success"]


# --- Borrado protegido --------------------------------------------------------------------


def test_service_of_running_revision_cannot_be_deleted(api, slug):
    api.service(slug, "web")
    api.service(slug, "otro")
    api.deploy(slug)
    assert api.get(url(slug)).json()["items"][0]["protected"] is True
    response = api.delete(url(slug, "web"))
    assert response.status_code == 409
    assert "forma parte del despliegue en funcionamiento" in response.json()["detail"]
    assert len(api.get(url(slug)).json()["items"]) == 2


def test_protection_ends_when_app_is_stopped(api, slug):
    api.service(slug, "web")
    api.deploy(slug)
    api.post(f"/api/applications/{slug}/stop")
    assert api.get(url(slug)).json()["items"][0]["protected"] is False
    assert api.delete(url(slug, "web")).status_code == 204


def test_new_service_is_not_protected_and_can_be_deleted(api, slug):
    api.service(slug, "web")
    api.deploy(slug)
    api.service(slug, "nuevo")  # no está en la revisión activa
    assert api.delete(url(slug, "nuevo")).status_code == 204


# --- Sesión y CSRF ------------------------------------------------------------------------


def test_routes_require_session(client, slug_unused=None):
    assert client.get(url("demo")).status_code == 401
    assert client.post(url("demo"), json={}).status_code == 401


def test_modifying_routes_require_csrf(logged_in, api, slug):
    api.service(slug, "web")
    client = logged_in.client
    assert client.post(url(slug), json={"name": "ex", "catalog_id": "whoami"}).status_code == 403
    assert client.patch(url(slug, "web"), json={"memory_mb": 48}).status_code == 403
    assert client.delete(url(slug, "web")).status_code == 403
