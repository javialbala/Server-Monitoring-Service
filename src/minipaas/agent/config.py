"""Configuración del agente, leída del entorno."""

import ipaddress
import os
from dataclasses import dataclass

from minipaas.common.naming import INSTANCE_RE
from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError


class ConfigError(Exception):
    """Valor de configuración inválido; el agente no debe arrancar."""


def _read_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw not in ("true", "false"):
        raise ConfigError(f"{name} debe ser «true» o «false» (valor recibido: {raw!r}).")
    return raw == "true"


@dataclass(frozen=True)
class AgentSettings:
    token_file: str
    # Instalación a la que pertenece este agente: solo toca recursos con su misma etiqueta.
    instance: str = "dev"
    # Dirección del host en la que se publican los puertos de las aplicaciones. Con 0.0.0.0
    # quedarían expuestas a toda la red: lo decide el administrador del servidor con esta
    # variable, NUNCA el usuario del panel (por eso no viaja en ninguna petición).
    publish_address: str = "127.0.0.1"
    # Habilita las entradas de prueba del catálogo (test-crash, test-unhealthy).
    enable_test_catalog: bool = False

    @classmethod
    def from_env(cls) -> "AgentSettings":
        token_file = os.environ.get(TOKEN_FILE_ENV)
        if not token_file:
            raise TokenError(f"Falta la variable de entorno {TOKEN_FILE_ENV}.")
        instance = os.environ.get("MINIPAAS_INSTANCE", "dev")
        if not INSTANCE_RE.match(instance):
            raise ConfigError(f"MINIPAAS_INSTANCE no es válida: {instance!r}.")
        address = os.environ.get("MINIPAAS_PUBLISH_ADDRESS", "127.0.0.1")
        try:
            ipaddress.IPv4Address(address)
        except ValueError:
            raise ConfigError(
                f"MINIPAAS_PUBLISH_ADDRESS no es una IPv4 válida: {address!r}."
            ) from None
        return cls(
            token_file=token_file,
            instance=instance,
            publish_address=address,
            enable_test_catalog=_read_bool("MINIPAAS_ENABLE_TEST_CATALOG", False),
        )
