"""
Serviço de listagem de ativos.

Consulta a brapi.dev e retorna ativos disponíveis com filtros.
"""

from __future__ import annotations

from typing import Any

from app.repositories.brapi.client import BrapiClient


class AssetService:
    """Serviço de consulta de ativos disponíveis."""

    def __init__(self, brapi_client: BrapiClient) -> None:
        self._brapi = brapi_client

    async def list_assets(
        self, search: str | None = None, sector: str | None = None
    ) -> list[dict[str, Any]]:
        """Lista ativos disponíveis com filtros."""
        raw = await self._brapi.list_assets(search=search, sector=sector)
        stocks = raw.get("stocks", [])

        return [
            {
                "ticker": s.get("stock", ""),
                "name": s.get("name", ""),
                "type": s.get("type", "stock"),
                "sector": s.get("sector"),
                "logo": s.get("logo"),
            }
            for s in stocks
        ]

    async def available(self) -> list[dict[str, Any]]:
        """Lista simplificada de ativos."""
        raw = await self._brapi.available()
        symbols = raw.get("symbols", [])
        return [
            {"ticker": s.get("symbol", ""), "name": s.get("name", "")} for s in symbols
        ]
