"""Rutas de aplicaciones. Todas requieren sesión; las que modifican, también CSRF."""

from fastapi import APIRouter, HTTPException, Request

from minipaas.controlplane.api.deps import (
    ConnectionDep,
    CsrfDep,
    SessionDep,
    client_ip,
)
from minipaas.controlplane.schemas import (
    ApplicationCreate,
    ApplicationList,
    ApplicationOut,
    ApplicationUpdate,
)
from minipaas.controlplane.services.applications import (
    ApplicationNotFound,
    InvalidSlug,
    SlugAlreadyExists,
)

router = APIRouter(prefix="/api/applications")

NOT_FOUND = HTTPException(404, "Aplicación no encontrada")


@router.get("")
def list_applications(
    request: Request,
    _: SessionDep,
    conn: ConnectionDep,
) -> ApplicationList:
    items = request.app.state.applications.list(conn)
    return ApplicationList(items=[ApplicationOut.from_application(a) for a in items])


@router.post("", status_code=201)
def create_application(
    body: ApplicationCreate,
    request: Request,
    current: CsrfDep,
    conn: ConnectionDep,
) -> ApplicationOut:
    try:
        application = request.app.state.applications.create(
            conn, body.name, body.slug, body.description, current.user.id, client_ip(request)
        )
    except InvalidSlug as error:
        raise HTTPException(422, str(error)) from None
    except SlugAlreadyExists:
        raise HTTPException(409, "Ya existe una aplicación con ese identificador") from None
    return ApplicationOut.from_application(application)


@router.get("/{slug}")
def get_application(
    slug: str,
    request: Request,
    _: SessionDep,
    conn: ConnectionDep,
) -> ApplicationOut:
    try:
        return ApplicationOut.from_application(request.app.state.applications.get(conn, slug))
    except ApplicationNotFound:
        raise NOT_FOUND from None


@router.patch("/{slug}")
def update_application(
    slug: str,
    body: ApplicationUpdate,
    request: Request,
    current: CsrfDep,
    conn: ConnectionDep,
) -> ApplicationOut:
    try:
        application = request.app.state.applications.update(
            conn, slug, body.name, body.description, current.user.id, client_ip(request)
        )
    except ApplicationNotFound:
        raise NOT_FOUND from None
    return ApplicationOut.from_application(application)


@router.delete("/{slug}", status_code=204)
def delete_application(
    slug: str,
    request: Request,
    current: CsrfDep,
    conn: ConnectionDep,
) -> None:
    try:
        request.app.state.lifecycle.delete_application(
            conn, slug, current.user.id, client_ip(request)
        )
    except ApplicationNotFound:
        raise NOT_FOUND from None
