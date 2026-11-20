import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from server_monitor.panel.agent_client import AgentError
from server_monitor.panel.security.csrf import CSRF_HEADER, csrf_token_is_valid
from server_monitor.panel.security.passwords import (
    MAX_PASSWORD_LENGTH,
    verify_password,
)
from server_monitor.panel.security.sessions import Session

SESSION_COOKIE = "sms_session"

logger = logging.getLogger("server_monitor.access")

router = APIRouter(prefix="/api")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


def client_ip(request: Request) -> str:
    # Detrás de un proxy inverso sería la IP del proxy.
    return request.client.host if request.client else "unknown"


def current_session(request: Request) -> Session | None:
    raw_token = request.cookies.get(SESSION_COOKIE)
    return request.app.state.sessions.get(raw_token) if raw_token else None


def require_session(request: Request) -> Session:
    session = current_session(request)
    if session is None:
        raise HTTPException(401, "Sesión no iniciada o caducada")
    return session


def require_csrf(request: Request, session: Annotated[Session, Depends(require_session)]) -> None:
    if not csrf_token_is_valid(session.csrf_token, request.headers.get(CSRF_HEADER)):
        raise HTTPException(403, "Token CSRF ausente o no válido")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/session")
def session_status(request: Request) -> dict:
    session = current_session(request)
    return {
        "authenticated": session is not None,
        "csrf_token": session.csrf_token if session else None,
    }


@router.post("/login", status_code=204)
def login(body: LoginRequest, request: Request, response: Response) -> None:
    state = request.app.state
    ip = client_ip(request)

    retry_after = state.limiter.is_blocked(ip)
    if retry_after is not None:
        logger.warning("Login bloqueado por demasiados intentos fallidos (ip=%s)", ip)
        raise HTTPException(
            429,
            "Demasiados intentos fallidos. Inténtalo de nuevo más tarde.",
            headers={"Retry-After": str(retry_after)},
        )

    if not verify_password(state.password_hash, body.password):
        state.limiter.record_failure(ip)
        logger.warning("Login fallido (ip=%s)", ip)
        raise HTTPException(401, "Contraseña incorrecta")

    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        state.sessions.revoke(old_token)
    raw_token, _ = state.sessions.create()
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=int(state.sessions.absolute),
        path="/",
        httponly=True,
        samesite="strict",
        secure=state.settings.cookie_secure,
    )
    logger.info("Login correcto (ip=%s)", ip)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response) -> None:
    request.app.state.sessions.revoke(request.cookies[SESSION_COOKIE])
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    logger.info("Logout (ip=%s)", client_ip(request))


@router.get("/metrics", dependencies=[Depends(require_session)])
async def metrics(request: Request) -> dict:
    try:
        return await request.app.state.agent_client.metrics()
    except AgentError:
        raise HTTPException(502, "El agente no responde") from None


@router.get("/containers", dependencies=[Depends(require_session)])
async def containers(request: Request) -> dict:
    try:
        return await request.app.state.agent_client.containers()
    except AgentError:
        raise HTTPException(502, "El agente no responde") from None


@router.get("/images", dependencies=[Depends(require_session)])
async def images(request: Request) -> dict:
    try:
        return await request.app.state.agent_client.images()
    except AgentError:
        raise HTTPException(502, "El agente no responde") from None


@router.get("/docker", dependencies=[Depends(require_session)])
async def docker(request: Request) -> dict:
    try:
        return await request.app.state.agent_client.docker()
    except AgentError:
        raise HTTPException(502, "El agente no responde") from None
