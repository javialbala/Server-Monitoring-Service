"""Limitación de intentos fallidos de login, por dirección IP.

Limitación conocida: el estado está en memoria y asume UN solo proceso de uvicorn; se pierde
al reiniciar. Es aceptable: un atacante no puede reiniciar el servicio.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from math import ceil


class LoginRateLimiter:
    def __init__(
        self,
        max_failures: int,
        window_minutes: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window = window_minutes * 60  # segundos
        self.clock = clock
        self._lock = threading.Lock()
        # Ventana deslizante: instantes de los fallos de cada IP.
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, ip: str) -> deque[float]:
        failures = self._failures[ip]
        limit = self.clock() - self.window
        while failures and failures[0] <= limit:
            failures.popleft()
        if not failures:
            del self._failures[ip]
        return failures

    def is_blocked(self, ip: str) -> int | None:
        """Segundos hasta poder reintentar (para Retry-After), o None si no está bloqueada."""
        with self._lock:
            failures = list(self._recent(ip))
            if len(failures) < self.max_failures:
                return None
            # Se desbloquea cuando el fallo que completa el cupo sale de la ventana.
            oldest_counted = failures[-self.max_failures]
            return max(1, ceil(oldest_counted + self.window - self.clock()))

    def record_failure(self, ip: str) -> None:
        with self._lock:
            self._failures[ip].append(self.clock())
