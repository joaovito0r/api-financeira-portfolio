"""
Cliente HTTP singleton compartilhado.

Gerencia o ciclo de vida do httpx.AsyncClient para ser
reutilizado por toda a aplicação.
"""

from __future__ import annotations

import httpx


class HTTPClientManager:
    """Gerenciador do cliente HTTP singleton."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        """Retorna o cliente HTTP (cria se não existir)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        """Fecha o cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None


http_client = HTTPClientManager()
