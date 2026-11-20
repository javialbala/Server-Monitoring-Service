import docker
from fastapi import FastAPI, HTTPException

from server_monitor.agent import containers, host_metrics, images
from server_monitor.agent.config import AgentSettings

DOCKER_API_VERSION = "1.44"  # Docker Engine 25 o superior


def create_app(settings: AgentSettings, client: docker.DockerClient) -> FastAPI:
    # Solo rutas GET y sin documentación. No hay autenticación: el agente solo es alcanzable
    # desde la red interna de Compose, compartida únicamente con el panel.
    app = FastAPI(
        title="Server Monitoring Service agent", docs_url=None, redoc_url=None, openapi_url=None
    )

    # `def` y no `async def`: FastAPI las ejecuta en un hilo y la medición de CPU no bloquea.
    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "docker": containers.docker_status(client)}

    @app.get("/metrics")
    def metrics() -> dict:
        return host_metrics.collect_metrics(
            hostfs=settings.hostfs, disks_dir=settings.disks_dir, net_dev=settings.net_dev
        )

    @app.get("/containers")
    def list_containers() -> dict:
        try:
            all_containers = containers.list_containers(client)
        except Exception:  # noqa: BLE001 - no se filtran detalles internos de Docker
            raise HTTPException(status_code=503, detail="Docker no está disponible") from None
        return {"collected_at": host_metrics.now_iso(), "containers": all_containers}

    @app.get("/images")
    def list_images() -> dict:
        try:
            found_images = images.list_images(client)
        except Exception:  # noqa: BLE001 - no se filtran detalles internos de Docker
            raise HTTPException(status_code=503, detail="Docker no está disponible") from None
        return {"collected_at": host_metrics.now_iso(), "images": found_images}

    return app


def build_app_from_env() -> FastAPI:
    # Con versión fija el cliente no consulta al daemon al crearse: el agente arranca aunque
    # Docker no esté disponible (/health lo indica) y se recupera solo.
    return create_app(AgentSettings.from_env(), docker.from_env(version=DOCKER_API_VERSION))
