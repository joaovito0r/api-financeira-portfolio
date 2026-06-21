"""Testes do serviço de listagem de ativos."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.repositories.local.cache_repo import GenericCacheRepository
from app.repositories.local.models import init_db
from app.services.asset_service import AssetService


@pytest.mark.asyncio
async def test_available_maps_real_brapi_shape() -> None:
    """`/api/available` da brapi devolve {"stocks": [<ticker str>, ...]}, sem nome."""
    await init_db()
    brapi = AsyncMock()
    brapi.available = AsyncMock(return_value={"stocks": ["PETR4", "VALE3"]})
    service = AssetService(brapi_client=brapi, cache_repo=GenericCacheRepository())

    result = await service.available()

    assert result == [{"ticker": "PETR4"}, {"ticker": "VALE3"}]
