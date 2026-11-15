"""Cliente HTTP del agente."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentHealth:
    reachable: bool
    docker_reachable: bool = False
    reason: str | None = None  # motivo corto, solo para uso interno/logs


class AgentClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
        )

    async def health(self) -> AgentHealth:
        """Consulta el agente. Nunca lanza: devuelve "no alcanzable" con un motivo."""
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            docker_ok = bool(response.json()["docker"]["reachable"])
        except httpx.HTTPStatusError as error:
            return self._unreachable(f"respuesta HTTP {error.response.status_code}")
        except httpx.HTTPError as error:
            return self._unreachable(f"error de conexión ({type(error).__name__})")
        except (ValueError, KeyError, TypeError):
            return self._unreachable("respuesta inválida")
        return AgentHealth(reachable=True, docker_reachable=docker_ok)

    @staticmethod
    def _unreachable(reason: str) -> AgentHealth:
        logger.error("El agente no está disponible: %s", reason)
        return AgentHealth(reachable=False, reason=reason)

    async def aclose(self) -> None:
        await self._client.aclose()
