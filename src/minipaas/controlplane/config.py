"""Configuración del panel, leída de variables de entorno."""

import os
from dataclasses import dataclass

from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError

# Ruta de un archivo, no una contraseña (falso positivo de bandit).
DEFAULT_PASSWORD_HASH_FILE = "/data/password_hash"  # noqa: S105


class ConfigError(Exception):
    """Un valor de configuración no es válido; el proceso no debe arrancar."""


def _read_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    if value.lower() not in ("true", "false"):
        raise ConfigError(f"{name} debe ser 'true' o 'false' (valor recibido: {value!r}).")
    return value.lower() == "true"


@dataclass(frozen=True)
class ControlPlaneSettings:
    agent_url: str
    token_file: str
    agent_timeout: float = 3.0
    # Archivo con el hash Argon2id de la contraseña (lo crea `manage set-password`).
    password_hash_file: str = DEFAULT_PASSWORD_HASH_FILE
    # La cookie solo viaja por HTTPS si es true. Debe activarse en cuanto haya HTTPS
    # (en desarrollo local se sirve por HTTP y el navegador descartaría la cookie).
    cookie_secure: bool = False
    session_idle_minutes: int = 30
    session_absolute_hours: int = 8
    login_max_failures: int = 5
    login_window_minutes: int = 15

    def __post_init__(self) -> None:
        for name in (
            "session_idle_minutes",
            "session_absolute_hours",
            "login_max_failures",
            "login_window_minutes",
        ):
            if getattr(self, name) < 1:
                raise ConfigError(f"{name} debe ser un entero positivo.")
        if not self.password_hash_file:
            raise ConfigError("MINIPAAS_PASSWORD_HASH_FILE no puede estar vacío.")

    @classmethod
    def from_env(cls) -> "ControlPlaneSettings":
        token_file = os.environ.get(TOKEN_FILE_ENV)
        if not token_file:
            raise TokenError(f"Falta la variable de entorno {TOKEN_FILE_ENV}.")
        return cls(
            agent_url=os.environ.get("MINIPAAS_AGENT_URL", "http://agent:8001"),
            token_file=token_file,
            password_hash_file=os.environ.get(
                "MINIPAAS_PASSWORD_HASH_FILE", DEFAULT_PASSWORD_HASH_FILE
            ),
            cookie_secure=_read_bool("MINIPAAS_COOKIE_SECURE", default=False),
        )
