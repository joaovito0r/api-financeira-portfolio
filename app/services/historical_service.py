"""
Serviço de histórico OHLCV.

Cache-first: dados históricos são imutáveis, salvos localmente.
"""

from __future__ import annotations

from typing import Any

from app.repositories.brapi.client import BrapiClient
from app.repositories.local.ohlcv_repo import LocalOHLCVRepository


class HistoricalService:
    """Serviço de consulta de histórico OHLCV."""

    def __init__(
        self,
        brapi_client: BrapiClient,
        local_repo: LocalOHLCVRepository,
    ) -> None:
        self._brapi = brapi_client
        self._local = local_repo

    async def get_history(
        self,
        ticker: str,
        range: str = "1y",
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """Busca histórico OHLCV com cache."""
        # 1. Tenta cache local
        cached = await self._local.get(ticker)
        if cached:
            return cached

        # 2. Cache miss: busca na brapi.dev
        raw = await self._brapi.historical(ticker, range=range, interval=interval)
        raw_history = raw.get("results", [{}])[0].get("historicalDataPrice", [])

        if not raw_history:
            return []

        # 3. Salva no cache
        return await self._local.save(ticker, raw_history)
