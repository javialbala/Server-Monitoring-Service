"""Errores de dominio comunes de los casos de uso de la Fase 3.

Cada uno lleva el código HTTP con el que se muestra: un único manejador en `main.py` los
convierte en `{"detail": mensaje}`, así las rutas no repiten `try/except`.
"""


class ServiceError(Exception):
    status_code = 500
    reason = "error"  # código corto para la auditoría

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    status_code = 404
    reason = "not_found"


class Conflict(ServiceError):
    status_code = 409
    reason = "conflict"


class Invalid(ServiceError):
    status_code = 422
    reason = "invalid"


class BadGateway(ServiceError):
    """El agente o Docker respondieron con un error."""

    status_code = 502
    reason = "agent_error"


class AgentDown(ServiceError):
    """No se pudo contactar con el agente."""

    status_code = 503
    reason = "agent_unreachable"

    def __init__(self, message: str = "No se puede contactar con el agente") -> None:
        super().__init__(message)


OPERATION_IN_PROGRESS = "Ya hay una operación en curso para esta aplicación"
