"""Dependencias comunes de las rutas: conexión, sesión y CSRF."""

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from minipaas.controlplane.repositories import users as users_repo
from minipaas.controlplane.repositories.sessions import Session
from minipaas.controlplane.repositories.users import User
from minipaas.controlplane.security.csrf import CSRF_HEADER, csrf_token_is_valid

SESSION_COOKIE = "minipaas_session"


@dataclass(frozen=True)
class CurrentSession:
    session: Session
    user: User


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    """Una conexión por petición, que se cierra SIEMPRE al terminar."""
    conn = request.app.state.db.connect()
    try:
        yield conn
    finally:
        conn.close()


def client_ip(request: Request) -> str:
    # Detrás de un proxy inverso request.client sería la IP del proxy: habrá que revisarlo
    # (cabecera X-Forwarded-For de confianza) cuando se añada uno.
    return request.client.host if request.client else "unknown"


def delete_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")


def find_session(request: Request, conn: sqlite3.Connection) -> CurrentSession | None:
    """Sesión válida de la cookie de la petición, o None. Solo lee (salvo last_seen_at,
    que es un metadato de la propia sesión y no datos de negocio)."""
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    session = request.app.state.sessions.resolve(conn, raw_token)
    if session is None:
        return None
    user = users_repo.get_by_id(conn, session.user_id)
    return CurrentSession(session, user) if user else None


ConnectionDep = Annotated[sqlite3.Connection, Depends(get_connection)]


def require_session(request: Request, conn: ConnectionDep) -> CurrentSession:
    current = find_session(request, conn)
    if current is None:
        # Si venía una cookie inválida o caducada, se borra del navegador.
        headers = None
        if request.cookies.get(SESSION_COOKIE):
            cleaner = Response()
            delete_session_cookie(cleaner)
            headers = {"set-cookie": cleaner.headers["set-cookie"]}
        raise HTTPException(401, "Sesión no iniciada o caducada", headers=headers)
    return current


SessionDep = Annotated[CurrentSession, Depends(require_session)]


def require_csrf(request: Request, current: SessionDep) -> CurrentSession:
    if not csrf_token_is_valid(current.session.csrf_token, request.headers.get(CSRF_HEADER)):
        raise HTTPException(403, "Token CSRF ausente o no válido")
    return current


# Sesión válida + token CSRF correcto: para todas las rutas que modifican datos.
CsrfDep = Annotated[CurrentSession, Depends(require_csrf)]
