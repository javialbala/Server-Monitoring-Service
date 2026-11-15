"""Errores de la API del agente: cada uno lleva su código HTTP y su código de error."""

import re


class AgentError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def invalid_request(detail: str) -> AgentError:
    return AgentError(400, "invalid_request", detail)


def not_found() -> AgentError:
    # Mismo mensaje exista o no el recurso: no se revela si hay algo ajeno con ese nombre.
    return AgentError(404, "not_found", "Recurso no encontrado")


def conflict(detail: str) -> AgentError:
    return AgentError(409, "conflict", detail)


_PATH_RE = re.compile(r"(?:/[\w.@:-]+){2,}")


def summarize_docker_error(error: Exception) -> str:
    """Resumen corto de un error de Docker, sin rutas internas (máximo 200 caracteres)."""
    text = getattr(error, "explanation", None) or "Docker rechazó la operación"
    first_line = str(text).strip().splitlines()[0] if str(text).strip() else "Error de Docker"
    return _PATH_RE.sub("<ruta>", first_line)[:200]
