"""Testes do serviço de histórico OHLCV — garante que range/interval são respeitados."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.repositories.local.models import init_db
from app.repositories.local.ohlcv_repo import LocalOHLCVRepository
from app.services.historical_service import HistoricalService


def _brapi_response(prices: list[dict]) -> dict:
    return {"results": [{"historicalDataPrice": prices}]}


@pytest.mark.asyncio
async def test_different_ranges_fetch_different_data() -> None:
    """Pedir um range/interval diferente pro mesmo ticker não devolve cache de outro."""
    await init_db()
    ticker = f"TST{uuid.uuid4().hex[:6].upper()}"

    short_history = [
        {"date": "2026-06-15", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ]
    long_history = [
        {"date": "2021-06-15", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2},
        {"date": "2026-06-15", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
    ]

    brapi = AsyncMock()
    brapi.historical = AsyncMock(
        side_effect=[_brapi_response(short_history), _brapi_response(long_history)]
    )
    service = HistoricalService(brapi_client=brapi, local_repo=LocalOHLCVRepository())

    first = await service.get_history(ticker, range="5d", interval="1d")
    second = await service.get_history(ticker, range="5y", interval="1mo")

    assert len(first) == 1
    assert len(second) == 2
    assert brapi.historical.call_count == 2


@pytest.mark.asyncio
async def test_same_range_and_interval_is_served_from_cache() -> None:
    """A mesma combinação ticker+range+interval não deve bater na brapi de novo."""
    await init_db()
    ticker = f"TST{uuid.uuid4().hex[:6].upper()}"
    history = [
        {"date": "2026-06-15", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ]

    brapi = AsyncMock()
    brapi.historical = AsyncMock(return_value=_brapi_response(history))
    service = HistoricalService(brapi_client=brapi, local_repo=LocalOHLCVRepository())

    await service.get_history(ticker, range="1y", interval="1d")
    await service.get_history(ticker, range="1y", interval="1d")

    assert brapi.historical.call_count == 1
