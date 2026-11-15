import json
import uuid

import pytest

SECRET = "valor-secreto-9876"
DEPLOYMENT_FIELDS = {
    "revision", "operation_id", "status", "status_label", "is_active", "previous_revision",
    "error", "created_at", "started_at", "finished_at", "services",
}  # fmt: skip


def base(slug="demo"):
    return f"/api/applications/{slug}"


@pytest.fixture
def slug(api):
    return api.app("demo")


def names(rows, key):
    return [r[key] for r in rows]


def audit_types(query):
    return [
        (r["event_type"], r["outcome"]) for r in query("SELECT * FROM audit_events ORDER BY id")
    ]


def test_first_deployment(api, slug, fake_agent, query):
    api.service(slug, "web", publish=True)
    result = api.deploy(slug)
    assert result["status"] == "healthy" and result["status_label"] == "Funcionando"
    assert (result["revision"], result["is_active"], result["previous_revision"]) == (1, True, None)
    assert result["finished_at"] and result["started_at"] and result["error"] is None
    application = api.application(slug)
    assert application["status"] == "running" and application["active_revision"] == 1
    assert application["operation_in_progress"] is False
    assert len(fake_agent.names(slug)) == 1 and fake_agent.networks == {slug}
    steps = names(result["events"], "step")
    assert steps[0] == "prepare" and steps[-1] == "result"
    assert all(e["outcome"] != "failure" for e in result["events"])
    assert [
        t
        for t in audit_types(query)
        if not t[0].startswith(("admin", "auth", "service", "database"))
    ] == [
        ("application.create", "success"),
        ("deployment.revision_create", "success"),
        ("deployment.request", "success"),
        ("deployment.start", "success"),
        ("deployment.success", "success"),
    ]


def test_deployment_shape_and_services(api, slug):
    api.service(slug, "web", env={"WHOAMI_NAME": SECRET}, publish=True)
    body = api.deploy(slug)
    assert set(body) == DEPLOYMENT_FIELDS | {"events"}
    service = body["services"][0]
    assert set(service) == {
        "name", "catalog_id", "catalog_name", "image_ref", "internal_port", "host_port",
        "memory_mb", "cpus", "env_names",
    }  # fmt: skip
    assert service["env_names"] == ["WHOAMI_NAME"] and service["host_port"] == 20000
    assert service["image_ref"].startswith("traefik/whoami@sha256:")
    assert SECRET not in json.dumps(api.get(f"{base()}/deployments").json())
    assert SECRET not in json.dumps(body)


def test_second_revision_replaces_first(api, slug, fake_agent):
    api.service(slug, "web", publish=True)
    api.deploy(slug)
    api.patch(f"{base()}/services/web", {"memory_mb": 64})
    second = api.deploy(slug)
    assert (second["revision"], second["previous_revision"], second["status"]) == (2, 1, "healthy")
    items = api.get(f"{base()}/deployments").json()["items"]
    assert names(items, "revision") == [2, 1]  # la más reciente primero
    assert names(items, "status") == ["healthy", "superseded"]
    assert names(items, "is_active") == [True, False]
    assert api.application(slug)["active_revision"] == 2
    assert [fake_agent.state_of(n) for n in fake_agent.names(slug)] == ["running"]
    assert fake_agent.names(slug)[0].endswith("-web-r2")  # la anterior se borró


def test_history_is_immutable(api, slug):
    api.service(slug, "web", memory_mb=32)
    api.deploy(slug)
    api.patch(f"{base()}/services/web", {"memory_mb": 96, "env": {"WHOAMI_NAME": "otro"}})
    first = api.get(f"{base()}/deployments/1").json()
    assert first["services"][0]["memory_mb"] == 32 and first["services"][0]["env_names"] == []
    api.post(f"{base()}/stop")
    api.delete(f"{base()}/services/web")
    assert api.get(f"{base()}/deployments/1").json()["services"][0]["name"] == "web"


def test_two_services(api, slug, fake_agent):
    api.service(slug, "web", publish=True)
    api.service(slug, "api", catalog_id="nginx-static")
    result = api.deploy(slug)
    assert result["status"] == "healthy"
    assert names(result["services"], "name") == ["web", "api"]
    assert len(fake_agent.names(slug)) == 2
    assert {fake_agent.state_of(n) for n in fake_agent.names(slug)} == {"running"}
    deploying = [e for e in result["events"] if e["step"] == "deploy"]
    assert len(deploying) == 2


def test_revision_without_services_is_409(api, slug, query):
    response = api.revision(slug)
    assert response.status_code == 409
    assert response.json() == {"detail": "Añade al menos un servicio antes de desplegar"}
    assert query("SELECT * FROM deployments") == []
    assert ("deployment.revision_create", "failure") in audit_types(query)


def test_repeated_request_id_returns_same_revision(api, slug, query):
    api.service(slug, "web")
    request_id = str(uuid.uuid4())
    first = api.revision(slug, request_id)
    again = api.revision(slug, request_id)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["operation_id"] == again.json()["operation_id"]
    assert len(query("SELECT * FROM deployments")) == 1


def test_deploy_twice_runs_once(api, slug, fake_agent, query):
    api.service(slug, "web")
    api.revision(slug)
    first = api.post(f"{base()}/revisions/1/deploy")
    second = api.post(f"{base()}/revisions/1/deploy")
    assert (first.status_code, second.status_code) == (202, 200)
    assert second.json()["status"] == "healthy"
    assert fake_agent.count("create") == 1
    assert audit_types(query).count(("deployment.start", "success")) == 1


def test_new_revision_discards_older_pending(api, slug):
    api.service(slug, "web")
    api.revision(slug)
    api.revision(slug)
    items = api.get(f"{base()}/deployments").json()["items"]
    assert names(items, "status") == ["pending", "discarded"]
    discarded = api.post(f"{base()}/revisions/1/deploy")  # idempotente: no hace nada
    assert discarded.status_code == 200 and discarded.json()["status"] == "discarded"


def test_invalid_request_id_and_unknown_revision(api, slug):
    api.service(slug, "web")
    assert api.post(f"{base()}/revisions", {"request_id": "no-es-uuid"}).status_code == 422
    assert api.post(f"{base()}/revisions", {}).status_code == 422
    assert api.post(f"{base()}/revisions/7/deploy").status_code == 404
    assert api.get(f"{base()}/deployments/7").status_code == 404
    assert api.get("/api/applications/nada/deployments").status_code == 404


def test_request_during_operation_in_progress_is_409(api, slug, app, query):
    api.service(slug, "web")
    api.revision(slug)
    # Simula una operación en curso: aquí no hay worker real que la mantenga abierta.
    conn = app.state.db.connect()
    conn.execute(
        "INSERT INTO deployments (application_id, revision, operation_id, request_id, status,"
        " created_at) VALUES (1, 5, ?, ?, 'deploying', 'x')",
        (str(uuid.uuid4()), str(uuid.uuid4())),
    )
    conn.close()
    assert api.application(slug)["operation_in_progress"] is True
    response = api.post(f"{base()}/revisions/1/deploy")
    assert response.status_code == 409
    assert response.json() == {"detail": "Ya hay una operación en curso para esta aplicación"}
    assert ("deployment.request", "failure") in audit_types(query)
    assert api.post(f"{base()}/stop").status_code == 409  # tampoco se puede parar
    assert api.delete(base()).status_code == 409  # ni borrar


def test_no_env_values_anywhere(api, slug, query, fake_agent):
    api.service(slug, "web", env={"WHOAMI_NAME": SECRET})
    api.deploy(slug)
    api.patch(f"{base()}/services/web", {"env": {"WHOAMI_NAME": SECRET + "2"}})
    fake_agent.fail("crash", "web", 2)
    api.deploy(slug)  # fallo + rollback
    api.post(f"{base()}/stop")
    api.post(f"{base()}/start")
    api.post(f"{base()}/recover")
    for table in ("audit_events", "deployments", "deployment_events"):
        assert SECRET not in json.dumps(query(f"SELECT * FROM {table}")), table  # noqa: S608


def test_routes_require_session_and_csrf(client, logged_in, api, slug):
    api.service(slug, "web")
    routes = [
        ("post", "/revisions"),
        ("post", "/revisions/1/deploy"),
        ("post", "/stop"),
        ("post", "/start"),
        ("post", "/recover"),
    ]
    for _, suffix in routes:
        assert logged_in.client.post(base() + suffix, json={}).status_code == 403  # sin CSRF
    gets = ["/deployments", "/deployments/1", "/runtime", "/services"]
    client.cookies.clear()
    for suffix in gets:
        assert client.get(base() + suffix).status_code == 401
    for _, suffix in routes:
        assert client.post(base() + suffix, json={}).status_code == 401
    assert client.get("/api/catalog").status_code == 401
