"""Rutas de revisiones, despliegue y ciclo de vida (los errores de dominio los convierte
`main.py`). Despliegue y recuperación automática corren en el worker; parar y arrancar, no."""

from dataclasses import asdict

from fastapi import APIRouter, Request, Response

from minipaas.common.catalog import CatalogError, get_entry
from minipaas.controlplane.api.deps import ConnectionDep, CsrfDep, SessionDep, client_ip
from minipaas.controlplane.schemas import (
    ApplicationOut,
    DeploymentDetailOut,
    DeploymentEventOut,
    DeploymentList,
    DeploymentOut,
    RevisionCreate,
    RuntimeOut,
)
from minipaas.controlplane.services.deployments import DeploymentView

router = APIRouter(prefix="/api/applications/{slug}")


def _catalog_namer(request: Request):
    include_test = request.app.state.settings.enable_test_catalog

    def name_of(catalog_id: str) -> str:
        try:
            return get_entry(catalog_id, include_test).name
        except CatalogError:
            return catalog_id

    return name_of


def _out(request: Request, view: DeploymentView) -> DeploymentOut:
    return DeploymentOut.from_view(view, _catalog_namer(request))


@router.post("/revisions", status_code=201)
def create_revision(
    slug: str,
    body: RevisionCreate,
    request: Request,
    response: Response,
    current: CsrfDep,
    conn: ConnectionDep,
) -> DeploymentOut:
    view, created = request.app.state.deployments.create_revision(
        conn, slug, body.request_id, current.user.id, client_ip(request)
    )
    response.status_code = 201 if created else 200  # 200: petición repetida, misma revisión
    return _out(request, view)


@router.post("/revisions/{revision}/deploy", status_code=202)
def deploy_revision(
    slug: str,
    revision: int,
    request: Request,
    response: Response,
    current: CsrfDep,
    conn: ConnectionDep,
) -> DeploymentOut:
    view, accepted = request.app.state.deployments.request_deploy(
        conn, slug, revision, current.user.id, client_ip(request)
    )
    response.status_code = 202 if accepted else 200  # 200: ya no estaba pendiente
    return _out(request, view)


@router.get("/deployments")
def list_deployments(
    slug: str, request: Request, _: SessionDep, conn: ConnectionDep
) -> DeploymentList:
    views = request.app.state.deployments.list(conn, slug)
    return DeploymentList(items=[_out(request, v) for v in views])


@router.get("/deployments/{revision}")
def get_deployment(
    slug: str, revision: int, request: Request, _: SessionDep, conn: ConnectionDep
) -> DeploymentDetailOut:
    view = request.app.state.deployments.get(conn, slug, revision)
    base = _out(request, view)
    events = [DeploymentEventOut(**asdict(e)) for e in view.events]
    return DeploymentDetailOut(**base.model_dump(), events=events)


@router.get("/runtime")
def get_runtime(slug: str, request: Request, _: SessionDep, conn: ConnectionDep) -> RuntimeOut:
    return RuntimeOut.from_view(request.app.state.lifecycle.runtime_view(conn, slug))


@router.post("/stop")
def stop_application(
    slug: str, request: Request, current: CsrfDep, conn: ConnectionDep
) -> ApplicationOut:
    application = request.app.state.lifecycle.stop(conn, slug, current.user.id, client_ip(request))
    return ApplicationOut.from_application(application)


@router.post("/start")
def start_application(
    slug: str, request: Request, current: CsrfDep, conn: ConnectionDep
) -> ApplicationOut:
    application = request.app.state.lifecycle.start(conn, slug, current.user.id, client_ip(request))
    return ApplicationOut.from_application(application)


@router.post("/recover")
def recover_application(
    slug: str, request: Request, current: CsrfDep, conn: ConnectionDep
) -> ApplicationOut:
    lifecycle = request.app.state.lifecycle
    application = lifecycle.recover(conn, slug, current.user.id, client_ip(request))
    return ApplicationOut.from_application(application)
