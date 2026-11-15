"""Limitación de intentos fallidos de login.

Limitación conocida: el estado está en memoria y asume UN solo proceso de uvicorn; se pierde
al reiniciar. Es aceptable aquí: un atacante no puede reiniciar el servicio, y con varios
procesos habría que mover el contador a la base de datos.
"""

import threading
from collections import defaultdict, deque
from datetime import timedelta
from math import ceil

from minipaas.controlplane.clock import Clock, utc_now


class LoginRateLimiter:
    def __init__(self, max_failures: int, window_minutes: int, clock: Clock = utc_now) -> None:
        self.max_failures = max_failures
        self.window = timedelta(minutes=window_minutes)
        self.clock = clock
        self._lock = threading.Lock()
        # Ventana deslizante: instantes de los fallos de cada clave ("ip:..." / "user:...").
        self._failures: dict[str, deque] = defaultdict(deque)

    def _recent(self, key: str) -> deque:
        failures = self._failures[key]
        limit = self.clock() - self.window
        while failures and failures[0] <= limit:
            failures.popleft()
        if not failures:
            del self._failures[key]
        return failures

    def is_blocked(self, ip: str, username: str) -> int | None:
        """Segundos hasta poder reintentar (para Retry-After), o None si no está bloqueado."""
        now = self.clock()
        wait = 0.0
        with self._lock:
            for key in (f"ip:{ip}", f"user:{username.lower()}"):
                failures = list(self._recent(key))
                if len(failures) >= self.max_failures:
                    # Se desbloquea cuando el fallo que completa el cupo sale de la ventana.
                    oldest_counted = failures[-self.max_failures]
                    wait = max(wait, (oldest_counted + self.window - now).total_seconds())
        return max(1, ceil(wait)) if wait > 0 else None

    def record_failure(self, ip: str, username: str) -> None:
        now = self.clock()
        with self._lock:
            self._failures[f"ip:{ip}"].append(now)
            self._failures[f"user:{username.lower()}"].append(now)

    def reset_username(self, username: str) -> None:
        """Tras un login correcto se olvidan los fallos de ese usuario (no los de la IP)."""
        with self._lock:
            self._failures.pop(f"user:{username.lower()}", None)
