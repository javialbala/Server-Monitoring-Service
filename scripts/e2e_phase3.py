"""Prueba extremo a extremo de la Fase 3 contra contenedores reales.

La lanza `scripts/e2e_phase3.sh`, que levanta un proyecto Compose SEPARADO (`minipaas-e2e`,
instancia `e2e`, puerto 8010, catálogo de prueba activado) y crea el administrador. Este script
recorre el flujo por la API del control plane, como lo haría el panel, y comprueba con el SDK de
Docker (solo lectura, salvo los contenedores de comprobación que crea y borra él mismo) lo que ha
ocurrido de verdad. Nunca toca recursos que no sean de la instancia `e2e`.
"""

import os
import sys
import time
import uuid

import docker
import httpx

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8010")
PASSWORD = os.environ["E2E_PASSWORD"]
INSTANCE = "e2e"
PROBE_IMAGE = (
    "nginxinc/nginx-unprivileged@sha256:"
    "0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6"
)
CHECK_LABEL = "minipaas.e2e-check"  # contenedores de comprobación creados por este script

docker_client = docker.from_env()
results: list[tuple[bool, str]] = []


def step(ok: bool, description: str, detail: str = "") -> bool:
    results.append((ok, description))
    print(f"{'OK   ' if ok else 'FALLO'}  {description}" + (f"  [{detail}]" if detail else ""))
    return ok


class Panel:
    """Cliente de la API con sesión y token CSRF, como el navegador."""

    def __init__(self) -> None:
        self.http = httpx.Client(base_url=BASE, timeout=120)
        self.csrf = ""

    def login(self) -> int:
        response = self.http.post(
            "/api/auth/login", json={"username": "admin", "password": PASSWORD}
        )
        if response.status_code == 200:
            self.csrf = response.json()["csrf_token"]
        return response.status_code

    def get(self, path: str) -> httpx.Response:
        return self.http.get(path)

    def send(self, method: str, path: str, body: dict | None = None) -> httpx.Response:
        return self.http.request(method, path, json=body, headers={"X-CSRF-Token": self.csrf})


def wait_deployment(panel: Panel, slug: str, revision: int, limit: int = 240) -> dict:
    """Consulta el despliegue cada 2 s hasta que termina (como el panel)."""
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        data = panel.get(f"/api/applications/{slug}/deployments/{revision}").json()
        if data["status"] not in ("pending", "preparing", "deploying", "rolling_back"):
            return data
        time.sleep(2)
    raise TimeoutError(f"La revisión {revision} de {slug} no terminó en {limit} s")


def deploy(panel: Panel, slug: str) -> dict:
    created = panel.send(
        "POST", f"/api/applications/{slug}/revisions", {"request_id": str(uuid.uuid4())}
    )
    revision = created.json()["revision"]
    panel.send("POST", f"/api/applications/{slug}/revisions/{revision}/deploy")
    return wait_deployment(panel, slug, revision)


def runtime(panel: Panel, slug: str) -> dict:
    return panel.get(f"/api/applications/{slug}/runtime").json()


def run_check(network: str, command: list[str]) -> bool:
    """Ejecuta un contenedor de comprobación en una red de MiniPaaS y devuelve si tuvo éxito."""
    container = docker_client.containers.create(
        PROBE_IMAGE,
        entrypoint=[command[0]],
        command=command[1:],
        network=network,
        user="101:101",
        read_only=True,
        cap_drop=["ALL"],
        labels={CHECK_LABEL: "true"},
    )
    try:
        container.start()
        return container.wait(timeout=30)["StatusCode"] == 0
    finally:
        container.remove(force=True)


def e2e_containers() -> list:
    return docker_client.containers.list(
        all=True, filters={"label": [f"minipaas.instance={INSTANCE}"]}
    )


def main() -> int:
    foreign_before = {
        c.id
        for c in docker_client.containers.list(all=True)
        if c.labels.get("minipaas.instance") != INSTANCE
        and not c.labels.get("com.docker.compose.project", "").startswith("minipaas-e2e")
    }
    panel = Panel()
    step(panel.login() == 200, "1-2. Inicio de sesión")

    # 3. Crear aplicación
    created = panel.send("POST", "/api/applications", {"name": "E2E demo", "slug": "e2e-demo"})
    step(created.status_code == 201, "3. Crear aplicación «e2e-demo»", str(created.status_code))

    # 4. Dos servicios: uno publicado y otro solo interno
    web = panel.send(
        "POST",
        "/api/applications/e2e-demo/services",
        {"name": "web", "catalog_id": "whoami", "publish": True, "env": {"WHOAMI_NAME": "e2e"}},
    )
    static = panel.send(
        "POST",
        "/api/applications/e2e-demo/services",
        {"name": "static", "catalog_id": "nginx-static"},
    )
    step(
        web.status_code == 201 and static.status_code == 201,
        "4. Añadir dos servicios (whoami publicado + NGINX interno)",
        f"puerto asignado {web.json().get('host_port')}",
    )
    rejected = panel.send(
        "POST",
        "/api/applications/e2e-demo/services",
        {"name": "bad", "catalog_id": "whoami", "env": {"LD_PRELOAD": "x.so"}},
    )
    step(rejected.status_code == 422, "4b. Variable no autorizada rechazada (422)")

    # 5-6. Desplegar y comprobar
    first = deploy(panel, "e2e-demo")
    step(first["status"] == "healthy", "5. Desplegar revisión 1", first["status"])
    state = runtime(panel, "e2e-demo")
    running = {s["name"]: s for s in state["services"] if s["state"] == "running"}
    step(set(running) == {"web", "static"}, "6. Estado real: los dos servicios en ejecución")
    url = running.get("web", {}).get("access_url")
    page = httpx.get(url, timeout=10) if url else None
    step(
        page is not None and page.status_code == 200 and "Name: e2e" in page.text,
        "6b. El servicio publicado responde desde el host con su variable",
        url or "sin URL",
    )
    step(
        running.get("static", {}).get("access_url") is None,
        "6c. El servicio interno no se publica en el host",
    )

    internal_net = f"minipaas-{INSTANCE}-e2e-demo"
    step(
        run_check(
            internal_net, ["wget", "-q", "-T", "3", "-O", "/dev/null", "http://static:8080/"]
        ),
        "6d. Comunicación entre servicios por nombre (web → http://static:8080)",
    )
    step(
        not run_check(
            internal_net, ["wget", "-q", "-T", "3", "-O", "/dev/null", "http://1.1.1.1/"]
        ),
        "6e. La red de la aplicación no tiene salida a Internet",
    )
    app_containers = [c for c in e2e_containers() if c.labels.get("minipaas.role") == "service"]
    hardened = all(
        not c.attrs["Mounts"]
        and c.attrs["HostConfig"]["ReadonlyRootfs"]
        and not c.attrs["HostConfig"]["Privileged"]
        and c.attrs["HostConfig"]["CapDrop"] == ["ALL"]
        and c.attrs["HostConfig"]["Memory"] > 0
        and c.attrs["Config"]["User"] not in ("", "0", "root")
        and c.labels.get("minipaas.managed") == "true"
        and c.labels.get("minipaas.operation") == first["operation_id"]
        for c in app_containers
    )
    step(
        hardened and len(app_containers) == 2,
        "6f. Contenedores endurecidos (sin montajes, solo lectura, sin privilegios, límites)",
    )

    # Aislamiento entre aplicaciones
    panel.send("POST", "/api/applications", {"name": "E2E otra", "slug": "e2e-other"})
    panel.send(
        "POST", "/api/applications/e2e-other/services", {"name": "api", "catalog_id": "whoami"}
    )
    other = deploy(panel, "e2e-other")
    other_net = f"minipaas-{INSTANCE}-e2e-other"
    web_ip = next(
        c.attrs["NetworkSettings"]["Networks"][internal_net]["IPAddress"]
        for c in app_containers
        if c.labels.get("minipaas.service") == "web"
    )
    isolated = not run_check(
        other_net, ["wget", "-q", "-T", "3", "-O", "/dev/null", "http://static:8080/"]
    ) and not run_check(
        other_net, ["wget", "-q", "-T", "3", "-O", "/dev/null", f"http://{web_ip}:80/"]
    )
    step(
        other["status"] == "healthy" and isolated,
        "6g. Otra aplicación no alcanza los servicios de «e2e-demo» (ni por nombre ni por IP)",
    )

    # 7-8. Detener y arrancar
    stopped = panel.send("POST", "/api/applications/e2e-demo/stop")
    states = {s["state"] for s in runtime(panel, "e2e-demo")["services"]}
    step(
        stopped.status_code == 200
        and stopped.json()["status"] == "stopped"
        and states == {"exited"},
        "7. Detener: aplicación «Detenida» y contenedores parados",
    )
    started = panel.send("POST", "/api/applications/e2e-demo/start")
    states = {s["state"] for s in runtime(panel, "e2e-demo")["services"]}
    step(
        started.status_code == 200
        and started.json()["status"] == "running"
        and states == {"running"},
        "8. Arrancar: aplicación «En funcionamiento» de nuevo",
    )

    # 9-10. Revisión con fallo de arranque controlado -> rollback
    panel.send(
        "POST",
        "/api/applications/e2e-demo/services",
        {"name": "broken", "catalog_id": "test-crash"},
    )
    second = deploy(panel, "e2e-demo")
    app = panel.get("/api/applications/e2e-demo").json()
    page = httpx.get(url, timeout=10) if url else None
    leftovers = [
        c.name
        for c in e2e_containers()
        if c.labels.get("minipaas.operation") == second["operation_id"]
    ]
    step(
        second["status"] == "rolled_back"
        and app["active_revision"] == 1
        and app["status"] == "running"
        and page is not None
        and page.status_code == 200
        and not leftovers,
        "9-10. Revisión 2 con fallo de arranque: rollback a la revisión 1, que vuelve a responder",
        second.get("error") or "",
    )

    # Fallo de salud (arranca pero no responde) -> rollback
    panel.send("DELETE", "/api/applications/e2e-demo/services/broken")
    panel.send(
        "POST",
        "/api/applications/e2e-demo/services",
        {"name": "sick", "catalog_id": "test-unhealthy"},
    )
    third = deploy(panel, "e2e-demo")
    app = panel.get("/api/applications/e2e-demo").json()
    step(
        third["status"] == "rolled_back" and app["active_revision"] == 1,
        "10b. Revisión 3 que no supera la comprobación de salud: rollback a la revisión 1",
        third.get("error") or "",
    )

    # Primera versión fallida sin versión anterior
    panel.send("POST", "/api/applications", {"name": "E2E fallo", "slug": "e2e-fail"})
    crash = panel.send(
        "POST", "/api/applications/e2e-fail/services", {"name": "crash", "catalog_id": "test-crash"}
    )
    step(crash.status_code == 201, "10c-1. Servicio de prueba que falla al arrancar añadido")
    failed = deploy(panel, "e2e-fail")
    fail_left = [c.name for c in e2e_containers() if c.labels.get("minipaas.app") == "e2e-fail"]
    fail_nets = docker_client.networks.list(filters={"label": ["minipaas.app=e2e-fail"]})
    step(
        failed["status"] == "failed" and not fail_left and not fail_nets,
        "10c. Primera versión fallida: «failed», sin contenedores ni redes restantes",
    )

    # 11. Historial
    history = panel.get("/api/applications/e2e-demo/deployments").json()["items"]
    summary = [(d["revision"], d["status"], d["is_active"]) for d in history]
    step(
        summary[-3:]
        == [(3, "rolled_back", False), (2, "rolled_back", False), (1, "healthy", True)],
        "11. Historial: r3 y r2 recuperadas, r1 activa",
        str(summary),
    )
    detail = panel.get("/api/applications/e2e-demo/deployments/2").json()
    step(
        any(e["outcome"] == "failure" for e in detail["events"]),
        "11b. La bitácora de la revisión 2 explica el fallo",
    )

    # 13. Reinicio del control plane en mitad de un despliegue (operación interrumpida)
    created = panel.send(
        "POST", "/api/applications/e2e-demo/revisions", {"request_id": str(uuid.uuid4())}
    )
    revision = created.json()["revision"]
    panel.send("POST", f"/api/applications/e2e-demo/revisions/{revision}/deploy")
    in_flight = panel.get(f"/api/applications/e2e-demo/deployments/{revision}").json()
    operation = in_flight["operation_id"]
    time.sleep(4)  # la sonda de «sick» tarda hasta 45 s: el despliegue sigue en curso
    controlplane = docker_client.containers.list(
        filters={
            "label": [
                "com.docker.compose.project=minipaas-e2e",
                "com.docker.compose.service=controlplane",
            ]
        }
    )[0]
    controlplane.restart(timeout=5)
    for _ in range(60):  # esperar a que vuelva a responder
        try:
            if httpx.get(f"{BASE}/api/health", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    time.sleep(8)  # la recuperación automática se ejecuta en segundo plano tras arrancar
    interrupted = panel.get(f"/api/applications/e2e-demo/deployments/{revision}").json()
    app = panel.get("/api/applications/e2e-demo").json()
    orphans = [c.name for c in e2e_containers() if c.labels.get("minipaas.operation") == operation]
    page = httpx.get(url, timeout=10) if url else None
    step(
        in_flight["status"] in ("preparing", "deploying")
        and interrupted["status"] == "interrupted"
        and app["status"] == "running"
        and app["active_revision"] == 1
        and not orphans
        and page is not None
        and page.status_code == 200,
        "13. Reinicio del control plane durante un despliegue: «interrumpida», recuperada la r1",
        f"{in_flight['status']} -> {interrupted['status']}; app {app['status']}",
    )

    # 12. Limpieza a través de MiniPaaS (borrar aplicaciones retira sus recursos)
    for slug in ("e2e-demo", "e2e-other", "e2e-fail"):
        panel.send("DELETE", f"/api/applications/{slug}")
    left = [c.name for c in e2e_containers() if c.labels.get("minipaas.managed") == "true"]
    nets = docker_client.networks.list(filters={"label": [f"minipaas.instance={INSTANCE}"]})
    step(not left and not nets, "12. Borrar las aplicaciones retira sus contenedores y redes")

    foreign_after = {
        c.id
        for c in docker_client.containers.list(all=True)
        if c.labels.get("minipaas.instance") != INSTANCE
        and not c.labels.get("com.docker.compose.project", "").startswith("minipaas-e2e")
        and not c.labels.get(CHECK_LABEL)
    }
    step(foreign_before == foreign_after, "Los contenedores ajenos a la prueba no han cambiado")

    failures = [d for ok, d in results if not ok]
    print(f"\n{len(results) - len(failures)}/{len(results)} comprobaciones correctas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
