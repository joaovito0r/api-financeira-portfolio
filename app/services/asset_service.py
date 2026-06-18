"""
Serviço de listagem de ativos.

Consulta a brapi.dev e retorna ativos disponíveis com filtros (cache-first).
"""

from __future__ import annotations

from typing import Any

from app.core.cache import ASSET_LIST_CACHE
from app.repositories.brapi.client import BrapiClient
from app.repositories.local.cache_repo import GenericCacheRepository


class AssetService:
    """Serviço de consulta de ativos disponíveis (cache-first)."""

    def __init__(
        self, brapi_client: BrapiClient, cache_repo: GenericCacheRepository
    ) -> None:
        self._brapi = brapi_client
        self._cache = cache_repo

    async def list_assets(
        self, search: str | None = None, sector: str | None = None
    ) -> list[dict[str, Any]]:
        """Lista ativos disponíveis com filtros (cache por combinação de filtro)."""
        key = f"assets:all:{search or ''}:{sector or ''}"
        cached = await self._cache.get(key, ASSET_LIST_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        raw = await self._brapi.list_assets(search=search, sector=sector)
        stocks = raw.get("stocks", [])
        result = [
            {
                "ticker": s.get("stock", ""),
                "name": s.get("name", ""),
                "type": s.get("type", "stock"),
                "sector": s.get("sector"),
                "logo": s.get("logo"),
            }
            for s in stocks
        ]
        return await self._cache.save(key, result, ASSET_LIST_CACHE)  # type: ignore[no-any-return]

    async def available(self) -> list[dict[str, Any]]:
        """Lista simplificada de ativos (cache-first)."""
        key = "assets:available"
        cached = await self._cache.get(key, ASSET_LIST_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        raw = await self._brapi.available()
        symbols = raw.get("symbols", [])
        result = [
            {"ticker": s.get("symbol", ""), "name": s.get("name", "")} for s in symbols
        ]
        return await self._cache.save(key, result, ASSET_LIST_CACHE)  # type: ignore[no-any-return]
