"""Testes do serviço de listagem de ativos."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete

from app.repositories.local.cache_repo import GenericCacheRepository
from app.repositories.local.models import CacheEntryModel, get_session, init_db
from app.services.asset_service import AssetService


@pytest.fixture(autouse=True)
async def _clear_asset_cache() -> None:
    """`available()`/`list_assets()` usam chaves de cache fixas; isola cada teste."""
    await init_db()
    async with get_session() as session:
        await session.execute(delete(CacheEntryModel))
        await session.commit()


@pytest.mark.asyncio
async def test_available_enriches_with_name_from_list_assets() -> None:
    """`/api/available` da brapi só devolve tickers; o nome vem de /api/quote/list."""
    brapi = AsyncMock()
    brapi.available = AsyncMock(return_value={"stocks": ["PETR4", "VALE3"]})
    brapi.list_assets = AsyncMock(
        return_value={
            "stocks": [
                {"stock": "PETR4", "name": "PETROBRAS PN"},
                {"stock": "VALE3", "name": "VALE ON"},
            ]
        }
    )
    service = AssetService(brapi_client=brapi, cache_repo=GenericCacheRepository())

    result = await service.available()

    assert result == [
        {"ticker": "PETR4", "name": "PETROBRAS PN"},
        {"ticker": "VALE3", "name": "VALE ON"},
    ]


@pytest.mark.asyncio
async def test_available_falls_back_to_empty_name_when_unmatched() -> None:
    """Ticker presente em /api/available mas ausente em /api/quote/list não quebra."""
    brapi = AsyncMock()
    brapi.available = AsyncMock(return_value={"stocks": ["NOVO11"]})
    brapi.list_assets = AsyncMock(return_value={"stocks": []})
    service = AssetService(brapi_client=brapi, cache_repo=GenericCacheRepository())

    result = await service.available()

    assert result == [{"ticker": "NOVO11", "name": ""}]
