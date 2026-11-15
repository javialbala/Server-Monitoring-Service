"""Configuración del agente, leída del entorno."""

import os
from dataclasses import dataclass

from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError


@dataclass(frozen=True)
class AgentSettings:
    token_file: str

    @classmethod
    def from_env(cls) -> "AgentSettings":
        token_file = os.environ.get(TOKEN_FILE_ENV)
        if not token_file:
            raise TokenError(f"Falta la variable de entorno {TOKEN_FILE_ENV}.")
        return cls(token_file=token_file)
