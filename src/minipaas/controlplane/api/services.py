"""Rutas de los servicios de una aplicación (los errores de dominio los convierte `main.py`)."""

from fastapi import APIRouter, Request

from minipaas.controlplane.api.deps import ConnectionDep, CsrfDep, SessionDep, client_ip
from minipaas.controlplane.schemas import ServiceCreate, ServiceList, ServiceOut, ServiceUpdate

router = APIRouter(prefix="/api/applications/{slug}/services")


@router.get("")
def list_services(slug: str, request: Request, _: SessionDep, conn: ConnectionDep) -> ServiceList:
    views = request.app.state.app_services.list_services(conn, slug)
    return ServiceList(items=[ServiceOut.from_view(v) for v in views])


@router.post("", status_code=201)
def create_service(
    slug: str, body: ServiceCreate, request: Request, current: CsrfDep, conn: ConnectionDep
) -> ServiceOut:
    view = request.app.state.app_services.create(
        conn,
        slug,
        user_id=current.user.id,
        client_ip=client_ip(request),
        **body.model_dump(),
    )
    return ServiceOut.from_view(view)


@router.patch("/{name}")
def update_service(
    slug: str,
    name: str,
    body: ServiceUpdate,
    request: Request,
    current: CsrfDep,
    conn: ConnectionDep,
) -> ServiceOut:
    view = request.app.state.app_services.update(
        conn, slug, name, body.to_changes(), current.user.id, client_ip(request)
    )
    return ServiceOut.from_view(view)


@router.delete("/{name}", status_code=204)
def delete_service(
    slug: str, name: str, request: Request, current: CsrfDep, conn: ConnectionDep
) -> None:
    request.app.state.app_services.delete(conn, slug, name, current.user.id, client_ip(request))
