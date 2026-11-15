"""Sesiones en servidor: el navegador solo guarda un identificador aleatorio en una cookie."""

import hashlib
import secrets
import sqlite3
from datetime import timedelta

from minipaas.controlplane.clock import Clock, from_iso, to_iso, utc_now
from minipaas.controlplane.db.connection import transaction
from minipaas.controlplane.repositories import sessions as repo
from minipaas.controlplane.repositories.sessions import Session

# Solo se reescribe last_seen_at si han pasado más de 60 s desde la última vez:
# así no hay una escritura en la base de datos por cada petición.
TOUCH_INTERVAL = timedelta(seconds=60)
PURGE_AFTER = timedelta(days=1)


def hash_token(raw_token: str) -> str:
    """En la base de datos solo se guarda el SHA-256: un volcado de la BD no permite
    suplantar a nadie. SHA-256 (y no Argon2) basta porque el token tiene 256 bits de azar."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


class SessionService:
    def __init__(self, idle_minutes: int, absolute_hours: int, clock: Clock = utc_now) -> None:
        self.idle = timedelta(minutes=idle_minutes)
        self.absolute = timedelta(hours=absolute_hours)
        self.clock = clock

    def create(self, conn: sqlite3.Connection, user_id: int) -> tuple[str, Session]:
        raw_token = secrets.token_urlsafe(32)
        now = self.clock()
        session = repo.create(
            conn,
            hash_token(raw_token),
            user_id,
            csrf_token=secrets.token_urlsafe(32),
            now=to_iso(now),
            expires_at=to_iso(now + self.absolute),
        )
        return raw_token, session

    def resolve(self, conn: sqlite3.Connection, raw_token: str) -> Session | None:
        """Devuelve la sesión si es válida; None si no existe, está revocada o caducó."""
        session = repo.get_by_token_hash(conn, hash_token(raw_token))
        if session is None or session.revoked_at is not None:
            return None
        now = self.clock()
        if now >= from_iso(session.expires_at):
            return None
        idle_for = now - from_iso(session.last_seen_at)
        if idle_for > self.idle:
            return None
        if idle_for > TOUCH_INTERVAL:
            # last_seen_at es metadato de la propia sesión, no datos de negocio: por eso
            # las rutas GET pueden actualizarlo.
            with transaction(conn):
                repo.touch(conn, session.id, to_iso(now))
        return session

    def revoke(self, conn: sqlite3.Connection, session_id: int) -> None:
        repo.revoke(conn, session_id, to_iso(self.clock()))

    def revoke_all_for_user(self, conn: sqlite3.Connection, user_id: int) -> None:
        repo.revoke_all_for_user(conn, user_id, to_iso(self.clock()))

    def purge_expired(self, conn: sqlite3.Connection) -> int:
        """Borra las sesiones caducadas o revocadas hace más de un día."""
        return repo.delete_old(conn, to_iso(self.clock() - PURGE_AFTER))
