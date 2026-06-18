"""Testes do cache quente do universo observado."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from app.core import warm_cache
from app.repositories.local.models import (
    AlertModel,
    WatchlistItemModel,
    get_session,
    init_db,
)


@pytest.mark.asyncio
async def test_watched_universe_une_watchlist_e_alertas() -> None:
    await init_db()
    async with get_session() as session:
        session.add(WatchlistItemModel(watchlist_id="w1", ticker="PETR4"))
        session.add(
            AlertModel(
                user_id="u1", ticker="vale3", target_price=1, direction="above"
            )
        )
        await session.commit()
    universo = await warm_cache.watched_universe()
    assert "PETR4" in universo
    assert "VALE3" in universo  # normalizado p/ maiúsculas


@pytest.mark.asyncio
async def test_refresh_respeita_teto_de_tickers(monkeypatch) -> None:
    await init_db()
    async with get_session() as session:
        for i in range(5):
            session.add(WatchlistItemModel(watchlist_id="w1", ticker=f"TICK{i}"))
        await session.commit()

    monkeypatch.setattr(warm_cache.settings, "warm_cache_max_tickers", 3, raising=False)

    app = FastAPI()
    brapi = AsyncMock()
    brapi.quote = AsyncMock(return_value={"results": [{"regularMarketPrice": 10}]})
    app.state.brapi_client = brapi

    processados = await warm_cache.refresh_universe(app)
    assert processados <= 3
