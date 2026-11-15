"""Acceso al daemon de Docker (único componente que lo tiene)."""

from dataclasses import dataclass

import docker
from docker.errors import DockerException
from requests.exceptions import RequestException


@dataclass(frozen=True)
class DockerStatus:
    reachable: bool
    server_version: str | None


class DockerRuntime:
    """Envuelve el SDK de Docker. En esta fase solo comprueba que el daemon responde."""

    def __init__(self) -> None:
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        # Perezoso: así crear el objeto no exige que Docker esté disponible.
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def ping(self) -> DockerStatus:
        try:
            version = self._get_client().version()
            return DockerStatus(reachable=True, server_version=str(version.get("Version")))
        # DockerException: no se pudo crear el cliente (p. ej. no hay socket).
        # RequestException: el cliente existe pero Docker dejó de responder; el SDK
        # no la envuelve en DockerException.
        except (DockerException, RequestException):
            return DockerStatus(reachable=False, server_version=None)
