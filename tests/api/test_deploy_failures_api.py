"""Fallos del motor de despliegue y recuperación (con el agente falso)."""

import pytest

BASE = "/api/applications/demo"


@pytest.fixture
def slug(api):
    api.app("demo")
    return "demo"


def audit(query, prefix="deployment."):
    rows = query("SELECT event_type, outcome, metadata FROM audit_events ORDER BY id")
    return [(r["event_type"], r["outcome"]) for r in rows if r["event_type"].startswith(prefix)]


def events(result, outcome):
    return [e["message"] for e in result["events"] if e["outcome"] == outcome]


def assert_first_failure_left_nothing(fake_agent, slug="demo"):
    assert fake_agent.names(slug) == []
    assert slug not in fake_agent.networks  # sin versión anterior: las redes también se borran


def test_image_download_failure(api, slug, fake_agent, query):
    api.service(slug, "web")
    fake_agent.fail("pull", "whoami")
    result = api.deploy(slug)
    assert result["status"] == "failed" and result["status_label"] == "Fallida"
    assert "No se pudo descargar la imagen" in result["error"]
    assert events(result, "failure")
    assert api.application(slug)["status"] == "draft"
    assert api.application(slug)["active_revision"] is None
    assert_first_failure_left_nothing(fake_agent)
    assert audit(query) == [
        ("deployment.revision_create", "success"),
        ("deployment.request", "success"),
        ("deployment.start", "success"),
        ("deployment.failure", "failure"),
    ]


def test_container_creation_failure_removes_the_ones_already_created(api, slug, fake_agent):
    api.service(slug, "uno")
    api.service(slug, "dos")
    fake_agent.fail("create", "dos")
    result = api.deploy(slug)
    assert result["status"] == "failed"
    assert fake_agent.count("create") == 2 and fake_agent.count("cleanup") == 1
    assert_first_failure_left_nothing(fake_agent)


def test_service_that_stops_on_start(api, slug, fake_agent):
    api.service(slug, "web")
    fake_agent.fail("crash", "web")
    result = api.deploy(slug)
    assert result["status"] == "failed"
    assert result["error"] == "El servicio «web» se detuvo al arrancar (código 1)"
    assert_first_failure_left_nothing(fake_agent)


def test_service_that_never_gets_healthy(api, slug, fake_agent):
    api.service(slug, "web")
    fake_agent.fail("unhealthy", "web")
    result = api.deploy(slug)
    assert result["status"] == "failed"
    assert result["error"] == "El servicio «web» no respondió a la comprobación de salud en 45 s"
    assert fake_agent.count("probe") > 5  # reintentó hasta agotar el plazo
    assert_first_failure_left_nothing(fake_agent)


def test_agent_does_not_recognise_the_image(api, slug, fake_agent):
    api.service(slug, "web")
    fake_agent.fail("catalog_unknown")
    result = api.deploy(slug)
    assert result["status"] == "failed"
    assert result["error"] == "El agente no reconoce la imagen autorizada"
    assert fake_agent.count("create") == 0


def test_timeout_after_docker_acted_leaves_no_orphans(api, slug, fake_agent, query):
    api.service(slug, "web")
    fake_agent.fail("timeout_after", "create")
    result = api.deploy(slug)
    assert result["status"] == "failed"
    assert "No se pudo contactar con el agente" in result["error"]
    assert fake_agent.count("create") == 1  # Docker sí creó el contenedor...
    assert fake_agent.names(slug) == []  # ...y el cleanup de la operación lo borró
    assert ("agent.unreachable", "failure") in audit(query, "agent.")
    assert api.application(slug)["status"] == "draft"


def deployed_then_new_revision(api, fake_agent):
    api.service("demo", "web", publish=True)
    assert api.deploy("demo")["status"] == "healthy"
    api.patch(f"{BASE}/services/web", {"memory_mb": 48})


def test_rollback_restores_previous_revision(api, slug, fake_agent, query):
    deployed_then_new_revision(api, fake_agent)
    fake_agent.fail("crash", "web", 2)
    result = api.deploy(slug)
    assert result["status"] == "rolled_back"
    assert result["status_label"] == "Fallida · versión anterior recuperada"
    assert result["error"] == "El servicio «web» se detuvo al arrancar (código 1)"
    application = api.application(slug)
    assert application["status"] == "running" and application["active_revision"] == 1
    first = api.get(f"{BASE}/deployments/1").json()
    assert (first["status"], first["is_active"]) == ("healthy", True)
    [name] = fake_agent.names(slug)
    assert name.endswith("-web-r1") and fake_agent.state_of(name) == "running"
    assert audit(query)[-5:] == [
        ("deployment.request", "success"),
        ("deployment.start", "success"),
        ("deployment.failure", "failure"),
        ("deployment.rollback_start", "success"),
        ("deployment.rollback_success", "success"),
    ]
    runtime = api.get(f"{BASE}/runtime").json()
    assert runtime["services"][0]["state"] == "running" and runtime["unknown_containers"] == 0


def test_rollback_failure_needs_attention(api, slug, fake_agent, query):
    deployed_then_new_revision(api, fake_agent)
    fake_agent.fail("crash", "web", 2)
    fake_agent.fail("start_error", "web", 1)  # la anterior tampoco arranca
    result = api.deploy(slug)
    assert (
        result["status"] == "rollback_failed" and result["status_label"] == "Requiere intervención"
    )
    assert api.application(slug)["status"] == "attention"
    assert "no pudo completar" in result["error"]
    assert audit(query)[-1] == ("deployment.rollback_failure", "failure")
    assert fake_agent.names(slug, result["operation_id"]) == []  # la nueva se limpió igualmente


def test_rollback_to_a_stopped_revision_does_not_start_it(api, slug, fake_agent):
    deployed_then_new_revision(api, fake_agent)
    api.post(f"{BASE}/stop")
    fake_agent.fail("crash", "web", 2)
    result = api.deploy(slug)
    assert result["status"] == "rolled_back"
    assert api.application(slug)["status"] == "stopped"
    assert [fake_agent.state_of(n) for n in fake_agent.names(slug)] == ["exited"]


def test_agent_lost_while_deploying_first_revision(api, slug, fake_agent, query):
    api.service(slug, "web")

    def drop_agent(method, path):
        if path.endswith("/networks"):
            fake_agent.down = True  # a partir de aquí no contesta

    fake_agent.on_request = drop_agent
    result = api.deploy(slug)
    assert result["status"] == "failed"
    assert (
        "No se pudo contactar con el agente; revisa la aplicación y usa «Recuperar»"
        in result["error"]
    )
    assert api.application(slug)["status"] == "attention"
    assert ("agent.unreachable", "failure") in audit(query, "agent.")


def test_agent_lost_during_rollback(api, slug, fake_agent):
    deployed_then_new_revision(api, fake_agent)
    fake_agent.fail("crash", "web", 2)

    def drop_agent(method, path):
        if path.endswith("/cleanup"):  # justo al limpiar la operación fallida
            fake_agent.down = True

    fake_agent.on_request = drop_agent
    result = api.deploy(slug)
    assert result["status"] == "rollback_failed"
    assert api.application(slug)["status"] == "attention"
    assert "Recuperar" in result["error"]


def test_recover_after_agent_comes_back(api, slug, fake_agent):
    deployed_then_new_revision(api, fake_agent)
    fake_agent.fail("crash", "web", 2)
    fake_agent.on_request = lambda m, p: setattr(fake_agent, "down", p.endswith("/cleanup"))
    api.deploy(slug)
    fake_agent.on_request, fake_agent.down = None, False
    fake_agent.clear_faults()
    assert len(fake_agent.names(slug)) == 2  # quedó la nueva sin borrar y la anterior parada
    recovered = api.post(f"{BASE}/recover")
    assert recovered.status_code == 200 and recovered.json()["status"] == "running"
    [name] = fake_agent.names(slug)
    assert name.endswith("-r1") and fake_agent.state_of(name) == "running"


def test_shutdown_during_deploy_abandons_without_judging(api, slug, fake_agent, query):
    """Al apagar el control plane, la operación en curso no se marca como fallida ni se intenta
    un rollback (los clientes se cierran y los errores serían falsos): queda «en curso» para que
    el siguiente arranque la marque como interrumpida y la recupere."""
    api.service(slug, "web")
    first = api.deploy(slug)
    assert first["status"] == "healthy"

    engine = api.session.client.app.state.engine
    fake_agent.fail("unhealthy", "web", revision=2)

    def stop_on_probe(method, path):
        if path.endswith("/probe"):
            engine.request_stop()  # el apagado llega mientras se comprueba la salud

    fake_agent.on_request = stop_on_probe
    try:
        result = api.deploy(slug)
    finally:
        fake_agent.on_request = None
        engine.stopping.clear()

    assert result["status"] == "deploying"  # ni failed, ni rolled_back, ni rollback_failed
    assert result["error"] is None
    assert "se marcará como interrumpida" in " ".join(e["message"] for e in result["events"])
    assert ("deployment.failure", "failure") not in audit(query)
    assert api.application(slug)["active_revision"] == 1
