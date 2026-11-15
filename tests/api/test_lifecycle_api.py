"""Parar, arrancar, recuperar, borrar, estado real, reinicio y concurrencia."""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import PASSWORD, USERNAME, make_app
from fastapi.testclient import TestClient

BASE = "/api/applications/demo"


@pytest.fixture
def slug(api):
    api.app("demo")
    return "demo"


@pytest.fixture
def running(api, slug):
    api.service(slug, "web", publish=True)
    assert api.deploy(slug)["status"] == "healthy"
    return slug


def audit(query, prefix):
    rows = query("SELECT event_type, outcome FROM audit_events ORDER BY id")
    return [(r["event_type"], r["outcome"]) for r in rows if r["event_type"].startswith(prefix)]


# --- Parar y arrancar ---------------------------------------------------------------------


def test_stop_and_start(api, running, fake_agent, query):
    stopped = api.post(f"{BASE}/stop")
    assert stopped.status_code == 200
    assert (stopped.json()["status"], stopped.json()["status_label"]) == ("stopped", "Detenida")
    assert [fake_agent.state_of(n) for n in fake_agent.names(running)] == ["exited"]
    assert api.get(f"{BASE}/deployments/1").json()["status"] == "stopped"
    started = api.post(f"{BASE}/start")
    assert started.json()["status"] == "running"
    assert [fake_agent.state_of(n) for n in fake_agent.names(running)] == ["running"]
    assert api.get(f"{BASE}/deployments/1").json()["status"] == "healthy"
    assert audit(query, "application.s") == [
        ("application.stop", "success"),
        ("application.start", "success"),
    ]


def test_stop_and_start_require_the_right_state(api, slug, running):
    assert api.post(f"{BASE}/start").status_code == 409  # está en marcha
    api.post(f"{BASE}/stop")
    assert api.post(f"{BASE}/stop").status_code == 409  # ya está detenida


def test_stop_never_deployed_is_409(api, slug):
    assert api.post(f"{BASE}/stop").status_code == 409


def test_stop_with_agent_down_is_503_and_changes_nothing(api, running, fake_agent, query):
    fake_agent.down = True
    response = api.post(f"{BASE}/stop")
    assert (response.status_code, response.json()) == (
        503,
        {"detail": "No se puede contactar con el agente"},
    )
    assert api.application(running)["status"] == "running"
    assert audit(query, "application.stop") == [("application.stop", "failure")]
    assert ("agent.unreachable", "failure") in audit(query, "agent.")


def test_start_failure_is_502_and_needs_attention(api, running, fake_agent, query):
    api.post(f"{BASE}/stop")
    fake_agent.fail("crash", "web")
    response = api.post(f"{BASE}/start")
    assert response.status_code == 502
    assert response.json()["detail"].startswith("No se pudo arrancar: El servicio «web» se detuvo")
    assert api.application(running)["status"] == "attention"
    assert audit(query, "application.start") == [("application.start", "failure")]
    fake_agent.clear_faults()
    assert (
        api.post(f"{BASE}/recover").json()["status"] == "stopped"
    )  # sigue siendo la revisión detenida


def test_start_with_agent_down_is_503(api, running, fake_agent):
    api.post(f"{BASE}/stop")
    fake_agent.down = True
    assert api.post(f"{BASE}/start").status_code == 503
    assert api.application(running)["status"] == "attention"


# --- Estado real --------------------------------------------------------------------------


def test_runtime_reports_real_containers(api, running, fake_agent):
    body = api.get(f"{BASE}/runtime").json()
    assert body["agent_reachable"] is True and body["active_revision"] == 1
    assert body["unknown_containers"] == 0
    assert body["services"] == [
        {"name": "web", "revision": 1, "state": "running", "state_label": "En ejecución",
         "exit_code": None, "host_port": 20000, "access_url": "http://127.0.0.1:20000/"}
    ]  # fmt: skip
    api.post(f"{BASE}/stop")
    stopped = api.get(f"{BASE}/runtime").json()["services"][0]
    assert (stopped["state"], stopped["state_label"], stopped["access_url"]) == (
        "exited",
        "Detenido",
        None,
    )
    assert stopped["exit_code"] == 0


def test_runtime_with_agent_down(api, running, fake_agent):
    fake_agent.down = True
    response = api.get(f"{BASE}/runtime")
    assert response.status_code == 200
    assert response.json() == {
        "agent_reachable": False, "active_revision": 1, "services": [], "unknown_containers": 0,
    }  # fmt: skip


def test_runtime_never_deployed(api, slug):
    body = api.get(f"{BASE}/runtime").json()
    assert body == {
        "agent_reachable": True,
        "active_revision": None,
        "services": [],
        "unknown_containers": 0,
    }


# --- Borrar aplicación --------------------------------------------------------------------


def test_delete_with_deployments_asks_the_agent(api, running, fake_agent, query):
    assert api.delete(BASE).status_code == 204
    assert fake_agent.count("delete_app") == 1
    assert fake_agent.names(running) == [] and running not in fake_agent.networks
    assert api.get(BASE).status_code == 404
    assert (
        query("SELECT * FROM deployments") == []
        and query("SELECT * FROM deployment_services") == []
    )
    assert ("application.delete", "success") in audit(query, "application.")


def test_delete_with_agent_down_keeps_the_application(api, running, fake_agent, query):
    fake_agent.down = True
    response = api.delete(BASE)
    assert response.status_code == 503
    assert response.json()["detail"].startswith(
        "No se puede contactar con el agente; no se elimina"
    )
    assert api.get(BASE).status_code == 200
    assert ("application.delete", "failure") in audit(query, "application.")
    fake_agent.down = False
    assert api.delete(BASE).status_code == 204


def test_delete_without_revisions_does_not_call_the_agent(api, slug, fake_agent):
    api.service(slug, "web")
    assert api.delete(BASE).status_code == 204
    assert fake_agent.calls == []


def test_delete_failed_first_deployment(api, slug, fake_agent):
    api.service(slug, "web")
    fake_agent.fail("crash", "web")
    api.deploy(slug)
    assert api.delete(BASE).status_code == 204
    assert fake_agent.count("delete_app") == 1


# --- Recuperar y reinicio del control plane -----------------------------------------------


def make_interrupted(app, api, slug, fake_agent):
    """Deja una revisión 2 «a medias» (deploying) con sus contenedores, como tras un corte."""
    api.patch(f"{BASE}/services/web", {"memory_mb": 48})
    operation = api.revision(slug).json()["operation_id"]
    conn = app.state.db.connect()
    conn.execute(
        "UPDATE deployments SET status = 'deploying', started_at = 'x', previous_deployment_id = 1"
        " WHERE revision = 2"
    )
    conn.close()
    fake_agent.add_container(slug, "web", 2, operation, "created")
    return operation


def restart(settings, clock, fake_agent, cookie):
    client = TestClient(make_app(settings, clock, fake=fake_agent))
    client.__enter__()
    client.cookies.set("minipaas_session", cookie)
    return client


def test_restart_interrupts_operation_and_recover_cleans_known_containers(
    api, running, app, settings, clock, fake_agent, logged_in, query
):
    operation = make_interrupted(app, api, running, fake_agent)
    unknown = fake_agent.add_container(running, "fantasma", 7, str(uuid.uuid4()))
    fake_agent.down = True  # el agente tampoco está al arrancar: no hay recuperación automática
    client = restart(settings, clock, fake_agent, logged_in.cookie)
    try:
        second = client.get(BASE).json()
        assert second["status"] == "attention" and second["operation_in_progress"] is False
        rev = client.get(f"{BASE}/deployments/2").json()
        assert rev["status"] == "interrupted"
        assert rev["error"] == "Operación interrumpida por un reinicio del control plane"
        assert ("deployment.interrupted", "failure") in audit(query, "deployment.")
        fake_agent.down = False
        recovered = client.post(f"{BASE}/recover", json={}, headers=logged_in.headers).json()
        assert recovered["status"] == "attention"  # hay un contenedor desconocido
        assert fake_agent.names(running, operation) == []  # el conocido (revisión 2) se limpió
        assert unknown in fake_agent.names(running)  # el desconocido NO se toca
        assert client.get(f"{BASE}/runtime").json()["unknown_containers"] == 1
        assert [fake_agent.state_of(n) for n in fake_agent.names(running)].count("running") == 2
        del fake_agent.containers[unknown]  # el administrador lo retira
        again = client.post(f"{BASE}/recover", json={}, headers=logged_in.headers).json()
        assert again["status"] == "running" and again["active_revision"] == 1
    finally:
        client.__exit__(None, None, None)


def test_restart_recovers_automatically_when_agent_is_reachable(
    api, running, app, settings, clock, fake_agent, logged_in
):
    operation = make_interrupted(app, api, running, fake_agent)
    client = restart(settings, clock, fake_agent, logged_in.cookie)
    try:
        assert client.get(BASE).json()["status"] == "running"
        assert client.get(f"{BASE}/deployments/2").json()["status"] == "interrupted"
        assert fake_agent.names(running, operation) == []
    finally:
        client.__exit__(None, None, None)


def test_recover_never_deployed_removes_networks(api, slug, fake_agent):
    api.service(slug, "web")
    fake_agent.fail("create", "web")
    api.deploy(slug)
    fake_agent.networks.add(slug)
    body = api.post(f"{BASE}/recover").json()
    assert body["status"] == "draft" and slug not in fake_agent.networks


def test_recover_stopped_application_stays_stopped(api, running, fake_agent):
    api.post(f"{BASE}/stop")
    assert api.post(f"{BASE}/recover").json()["status"] == "stopped"


def test_recover_restarts_a_down_service(api, running, fake_agent, query):
    [name] = fake_agent.names(running)
    fake_agent.containers[name]["state"] = "exited"  # alguien lo paró por fuera
    assert api.post(f"{BASE}/recover").json()["status"] == "running"
    assert fake_agent.state_of(name) == "running"
    assert ("application.recover", "success") in audit(query, "application.")


def test_recover_with_unhealthy_active_revision_needs_attention(api, running, fake_agent, query):
    fake_agent.fail("unhealthy", "web")
    assert api.post(f"{BASE}/recover").json()["status"] == "attention"
    assert ("application.recover", "failure") in audit(query, "application.")


def test_recover_with_agent_down_is_503(api, running, fake_agent):
    fake_agent.down = True
    assert api.post(f"{BASE}/recover").status_code == 503


# --- Concurrencia -------------------------------------------------------------------------


@pytest.fixture
def threaded(settings, clock, fake_agent):
    """Aplicación con el worker real (hilos) en lugar del síncrono de los tests."""
    executor = ThreadPoolExecutor(max_workers=2)
    app = make_app(settings, clock, fake=fake_agent, executor=executor)
    with TestClient(app) as client:
        conn = app.state.db.connect()
        app.state.auth.create_admin(conn, USERNAME, PASSWORD, source="test")
        conn.close()
        login = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        yield app, client
    executor.shutdown(wait=True)


def wait_for(client, path, key, wanted, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if client.get(path).json()[key] in wanted:
            return
        time.sleep(0.02)
    raise AssertionError(f"{path}: {key} no llegó a {wanted}")


def test_second_operation_is_rejected_while_one_runs(threaded, fake_agent, query):
    app, client = threaded
    client.post("/api/applications", json={"name": "demo", "slug": "demo"})
    client.post(f"{BASE}/services", json={"name": "web", "catalog_id": "whoami"})
    reached, release = threading.Event(), threading.Event()

    def block_on_networks(method, path):
        if path.endswith("/networks"):
            reached.set()
            assert release.wait(10)

    fake_agent.on_request = block_on_networks
    first = client.post(f"{BASE}/revisions", json={"request_id": str(uuid.uuid4())}).json()
    assert client.post(f"{BASE}/revisions/{first['revision']}/deploy").status_code == 202
    assert reached.wait(10)
    try:
        assert client.get(BASE).json()["operation_in_progress"] is True
        again = client.post(f"{BASE}/revisions/1/deploy")  # la misma: idempotente
        assert (again.status_code, again.json()["status"]) == (200, "preparing")
        second = client.post(f"{BASE}/revisions", json={"request_id": str(uuid.uuid4())}).json()
        conflict = client.post(f"{BASE}/revisions/{second['revision']}/deploy")
        assert conflict.status_code == 409
        assert client.post(f"{BASE}/stop").status_code == 409
        assert client.delete(BASE).status_code == 409
    finally:
        release.set()
    wait_for(client, f"{BASE}/deployments/1", "status", ("healthy",))
    assert client.post(f"{BASE}/revisions/{second['revision']}/deploy").status_code == 202


def test_simultaneous_requests_for_the_same_revision_run_once(threaded, fake_agent):
    app, client = threaded
    client.post("/api/applications", json={"name": "demo", "slug": "demo"})
    client.post(f"{BASE}/services", json={"name": "web", "catalog_id": "whoami"})
    client.post(f"{BASE}/revisions", json={"request_id": str(uuid.uuid4())})
    barrier = threading.Barrier(2)
    results = []

    def request():
        conn = app.state.db.connect()
        try:
            barrier.wait()
            _, accepted = app.state.deployments.request_deploy(conn, "demo", 1, 1, "test")
            results.append(accepted)
        finally:
            conn.close()

    threads = [threading.Thread(target=request) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [False, True]
    wait_for(client, f"{BASE}/deployments/1", "status", ("healthy",))
    assert fake_agent.count("create") == 1
