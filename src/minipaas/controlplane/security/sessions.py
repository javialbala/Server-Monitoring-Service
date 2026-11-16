"""Sesiones en memoria del proceso: el navegador solo guarda un identificador aleatorio.

Se pierden al reiniciar el panel (hay que volver a iniciar sesión), lo cual es aceptable.
"""

import hashlib
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Session:
    csrf_token: str
    created_at: float
    last_seen_at: float


def hash_token(raw_token: str) -> str:
    """Se guarda solo el SHA-256 del token. Basta (no hace falta Argon2) porque el token
    tiene 256 bits de azar."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


class SessionStore:
    def __init__(
        self,
        idle_minutes: int,
        absolute_hours: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.idle = idle_minutes * 60  # segundos
        self.absolute = absolute_hours * 3600
        self.clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}  # hash del token -> sesión

    def _is_expired(self, session: Session, now: float) -> bool:
        return now - session.created_at >= self.absolute or now - session.last_seen_at > self.idle

    def create(self) -> tuple[str, Session]:
        """Devuelve (token en claro para la cookie, sesión)."""
        raw_token = secrets.token_urlsafe(32)
        now = self.clock()
        session = Session(csrf_token=secrets.token_urlsafe(32), created_at=now, last_seen_at=now)
        with self._lock:
            # Aprovecha para borrar las sesiones caducadas que nadie volvió a usar.
            expired = [key for key, s in self._sessions.items() if self._is_expired(s, now)]
            for key in expired:
                del self._sessions[key]
            self._sessions[hash_token(raw_token)] = session
        return raw_token, session

    def get(self, raw_token: str) -> Session | None:
        """La sesión si es válida (y renueva la inactividad); None si no existe o caducó."""
        key = hash_token(raw_token)
        now = self.clock()
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            if self._is_expired(session, now):
                del self._sessions[key]
                return None
            session.last_seen_at = now
            return session

    def revoke(self, raw_token: str) -> None:
        with self._lock:
            self._sessions.pop(hash_token(raw_token), None)
