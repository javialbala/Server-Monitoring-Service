"""Configuración del control plane, leída del entorno."""

import os
from dataclasses import dataclass

from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError


@dataclass(frozen=True)
class ControlPlaneSettings:
    agent_url: str
    token_file: str
    agent_timeout: float = 3.0

    @classmethod
    def from_env(cls) -> "ControlPlaneSettings":
        token_file = os.environ.get(TOKEN_FILE_ENV)
        if not token_file:
            raise TokenError(f"Falta la variable de entorno {TOKEN_FILE_ENV}.")
        return cls(
            agent_url=os.environ.get("MINIPAAS_AGENT_URL", "http://agent:8001"),
            token_file=token_file,
        )
