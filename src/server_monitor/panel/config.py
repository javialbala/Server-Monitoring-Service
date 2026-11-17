import os
from dataclasses import dataclass


class ConfigError(Exception):
    """Un valor de configuración no es válido; el proceso no debe arrancar."""


def _read_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if not value:
        return default
    if value.lower() not in ("true", "false"):
        raise ConfigError(f"{name} debe ser 'true' o 'false' (valor recibido: {value!r}).")
    return value.lower() == "true"


@dataclass(frozen=True)
class PanelSettings:
    agent_url: str = "http://agent:8001"
    agent_timeout: float = 3.0
    # La cookie solo viaja por HTTPS si es true; actívalo cuando haya HTTPS delante del panel.
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

    @classmethod
    def from_env(cls) -> "PanelSettings":
        return cls(
            agent_url=os.environ.get("SMS_AGENT_URL", cls.agent_url),
            cookie_secure=_read_bool("SMS_COOKIE_SECURE", default=False),
        )
