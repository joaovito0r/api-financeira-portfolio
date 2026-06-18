"""
Serviço de cotações.

Implementa a lógica de negócio: cache-first, fallback para
brapi.dev, persistência local.
"""

from __future__ import annotations

from typing import Any

from app.core.concurrency import gather_limited
from app.repositories.brapi.client import BrapiClient
from app.repositories.local.quote_repo import LocalQuoteRepository


class QuoteService:
    """Serviço de consulta de cotações.

    Fluxo:
    1. Verifica cache local (SQLite)
    2. Se cache válido → retorna
    3. Se cache expirado/ausente → busca na brapi.dev
    4. Salva no cache local → retorna
    """

    def __init__(
        self,
        brapi_client: BrapiClient,
        local_repo: LocalQuoteRepository,
    ) -> None:
        self._brapi = brapi_client
        self._local = local_repo

    async def get_quote(self, ticker: str) -> dict[str, Any]:
        """Busca cotação de um ativo com cache."""
        # 1. Tenta cache local
        cached = await self._local.get(ticker)
        if cached:
            return cached

        # 2. Cache miss: busca na brapi.dev
        raw = await self._brapi.quote(ticker)
        result = raw.get("results", [{}])[0]

        # 3. Salva no cache
        return await self._local.save(ticker, result)

    async def get_multiple_quotes(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Busca cotações de múltiplos ativos em paralelo (concorrência limitada)."""
        return await gather_limited(
            *(self.get_quote(ticker.strip().upper()) for ticker in tickers)
        )
