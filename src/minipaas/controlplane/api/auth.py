"""Rutas de autenticación."""

from fastapi import APIRouter, HTTPException, Request, Response

from minipaas.controlplane.api.deps import (
    SESSION_COOKIE,
    ConnectionDep,
    CsrfDep,
    SessionDep,
    client_ip,
    delete_session_cookie,
    find_session,
)
from minipaas.controlplane.repositories import users as users_repo
from minipaas.controlplane.schemas import LoginOut, LoginRequest, MeOut, SessionOut, UserOut
from minipaas.controlplane.services.auth import InvalidCredentials, TooManyAttempts

router = APIRouter(prefix="/api/auth")


@router.get("/session")
def session_status(request: Request, conn: ConnectionDep) -> SessionOut:
    """Público: el panel lo usa al cargar para saber qué pantalla mostrar."""
    current = find_session(request, conn)
    return SessionOut(
        authenticated=current is not None,
        setup_required=users_repo.count(conn) == 0,
        user=UserOut(username=current.user.username) if current else None,
        csrf_token=current.session.csrf_token if current else None,
    )


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    conn: ConnectionDep,
) -> LoginOut:
    state = request.app.state
    previous = find_session(request, conn)  # si ya había sesión, se revoca (nuevo identificador)
    try:
        raw_token, session, user = state.auth.login(
            conn,
            body.username,
            body.password,
            client_ip(request),
            previous.session if previous else None,
        )
    except InvalidCredentials:
        raise HTTPException(401, "Usuario o contraseña incorrectos") from None
    except TooManyAttempts as error:
        raise HTTPException(
            429,
            "Demasiados intentos fallidos. Inténtalo de nuevo más tarde.",
            headers={"Retry-After": str(error.retry_after)},
        ) from None
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=int(state.sessions.absolute.total_seconds()),
        path="/",
        httponly=True,
        samesite="strict",
        secure=state.settings.cookie_secure,
    )
    return LoginOut(user=UserOut(username=user.username), csrf_token=session.csrf_token)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    current: CsrfDep,
    conn: ConnectionDep,
) -> None:
    request.app.state.auth.logout(conn, current.session, client_ip(request))
    delete_session_cookie(response)


@router.get("/me")
def me(current: SessionDep) -> MeOut:
    return MeOut(username=current.user.username, created_at=current.user.created_at)
