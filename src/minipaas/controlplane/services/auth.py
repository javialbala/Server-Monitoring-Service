"""Casos de uso de autenticación: crear el administrador, iniciar y cerrar sesión."""

import sqlite3

from minipaas.controlplane.clock import Clock, to_iso, utc_now
from minipaas.controlplane.db.connection import transaction
from minipaas.controlplane.repositories import users as users_repo
from minipaas.controlplane.repositories.sessions import Session
from minipaas.controlplane.repositories.users import User
from minipaas.controlplane.security import passwords
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.security.sessions import SessionService
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 64


class InvalidCredentials(Exception):
    """Usuario o contraseña incorrectos (no se distingue cuál: no revelar si el usuario existe)."""


class TooManyAttempts(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Demasiados intentos; reintentar en {retry_after} s")
        self.retry_after = retry_after


class AdminAlreadyExists(Exception):
    """Ya hay un usuario: el administrador nunca se sobrescribe desde la CLI."""


class InvalidUsername(ValueError):
    pass


class AuthService:
    def __init__(
        self,
        sessions: SessionService,
        audit_service: AuditService,
        limiter: LoginRateLimiter,
        clock: Clock = utc_now,
    ) -> None:
        self.sessions = sessions
        self.audit = audit_service
        self.limiter = limiter
        self.clock = clock

    def login(
        self,
        conn: sqlite3.Connection,
        username: str,
        password: str,
        client_ip: str,
        previous_session: Session | None = None,
    ) -> tuple[str, Session, User]:
        retry_after = self.limiter.is_blocked(client_ip, username)
        if retry_after is not None:
            self._record_failure(conn, client_ip, "rate_limited")
            raise TooManyAttempts(retry_after)

        user = users_repo.get_by_username(conn, username)
        # Si el usuario no existe se verifica contra un hash ficticio: mismo coste, mismo error.
        hash_to_check = user.password_hash if user else passwords.DUMMY_HASH
        password_ok = passwords.verify_password(hash_to_check, password)
        if user is None or not password_ok:
            self.limiter.record_failure(client_ip, username)
            # No se guarda el usuario intentado: podría ser una contraseña escrita en su campo.
            self._record_failure(conn, client_ip, "invalid_credentials")
            raise InvalidCredentials

        new_hash = (
            passwords.hash_password(password)
            if passwords.needs_rehash(user.password_hash)
            else None
        )
        with transaction(conn):
            if previous_session is not None:
                # Renovación del identificador: el de antes deja de valer.
                self.sessions.revoke(conn, previous_session.id)
            self.sessions.purge_expired(conn)
            raw_token, session = self.sessions.create(conn, user.id)
            if new_hash:
                users_repo.update_password_hash(conn, user.id, new_hash, to_iso(self.clock()))
            self.audit.record(
                conn, audit.LOGIN, audit.SUCCESS, user_id=user.id, client_ip=client_ip
            )
        self.limiter.reset_username(username)
        return raw_token, session, user

    def _record_failure(self, conn: sqlite3.Connection, client_ip: str, reason: str) -> None:
        with transaction(conn):
            self.audit.record(
                conn,
                audit.LOGIN_FAILED,
                audit.FAILURE,
                client_ip=client_ip,
                metadata={"reason": reason},
            )

    def logout(self, conn: sqlite3.Connection, session: Session, client_ip: str) -> None:
        with transaction(conn):
            self.sessions.revoke(conn, session.id)
            self.audit.record(
                conn, audit.LOGOUT, audit.SUCCESS, user_id=session.user_id, client_ip=client_ip
            )

    def create_admin(
        self, conn: sqlite3.Connection, username: str, password: str, source: str
    ) -> User:
        """Crea el administrador inicial. Nunca modifica uno existente."""
        if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
            raise InvalidUsername(
                f"El usuario debe tener entre {MIN_USERNAME_LENGTH} y {MAX_USERNAME_LENGTH} "
                "caracteres."
            )
        passwords.validate_new_password(password)
        # El hash (lento) se calcula antes de tomar el bloqueo de escritura.
        password_hash = passwords.hash_password(password)
        try:
            with transaction(conn):
                if users_repo.count(conn) > 0:
                    raise AdminAlreadyExists
                user = users_repo.create(conn, username, password_hash, to_iso(self.clock()))
                self.audit.record(
                    conn,
                    audit.ADMIN_CREATE,
                    audit.SUCCESS,
                    user_id=user.id,
                    resource_type="user",
                    resource_id=str(user.id),
                    metadata={"source": source},
                )
        except AdminAlreadyExists:
            with transaction(conn):
                self.audit.record(
                    conn,
                    audit.ADMIN_CREATE,
                    audit.FAILURE,
                    metadata={"source": source, "reason": "already_exists"},
                )
            raise
        return user
