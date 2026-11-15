"""Lectura del token compartido entre control plane y agente."""

import os
from pathlib import Path

# Es el NOMBRE de una variable de entorno, no una contraseña (falso positivo de bandit).
TOKEN_FILE_ENV = "MINIPAAS_AGENT_TOKEN_FILE"  # noqa: S105
MIN_TOKEN_LENGTH = 32


class TokenError(Exception):
    """El token no está disponible o no es válido; el proceso no debe arrancar."""


def read_token(path: str | Path) -> str:
    """Lee el token desde un archivo (p. ej. un secret de Compose en /run/secrets).

    Se usa un archivo y no una variable de entorno porque las variables de entorno
    son visibles con `docker inspect` y se heredan por los procesos hijos; un archivo
    montado solo lo ve quien tenga acceso al sistema de ficheros del contenedor.
    """
    file = Path(path)
    try:
        token = file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise TokenError(f"No existe el archivo del token: {file}") from None
    except (OSError, UnicodeDecodeError) as error:
        raise TokenError(f"No se puede leer el archivo del token {file}: {error}") from error
    if len(token) < MIN_TOKEN_LENGTH:
        raise TokenError(
            f"El token de {file} es demasiado corto: mínimo {MIN_TOKEN_LENGTH} caracteres."
        )
    return token


def read_token_from_env() -> str:
    """Lee el token usando la ruta indicada en MINIPAAS_AGENT_TOKEN_FILE."""
    path = os.environ.get(TOKEN_FILE_ENV)
    if not path:
        raise TokenError(f"Falta la variable de entorno {TOKEN_FILE_ENV}.")
    return read_token(path)
