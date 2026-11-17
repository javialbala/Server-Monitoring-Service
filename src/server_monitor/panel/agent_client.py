import logging

import httpx

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """El agente no responde o devolvió un error."""


class AgentClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def _get(self, path: str) -> dict:
        try:
            response = await self._client.get(path)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            # Solo se registra el tipo de error: el detalle no debe llegar al navegador.
            logger.error("Fallo al consultar el agente (%s): %s", path, type(error).__name__)
            raise AgentError(path) from error

    async def metrics(self) -> dict:
        return await self._get("/metrics")

    async def containers(self) -> dict:
        return await self._get("/containers")

    async def aclose(self) -> None:
        await self._client.aclose()
