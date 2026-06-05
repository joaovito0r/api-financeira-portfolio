"""
Testes das rotas de cotações.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_quote(async_client: AsyncClient) -> None:
    """Verifica se a rota de cotação responde."""
    response = await async_client.get("/api/quote/PETR4")
    assert response.status_code in (200, 503, 504)
    if response.status_code == 200:
        data = response.json()
        assert "ticker" in data


@pytest.mark.asyncio
async def test_get_multiple_quotes(async_client: AsyncClient) -> None:
    """Verifica rota de múltiplas cotações."""
    response = await async_client.get("/api/quotes?tickers=PETR4,VALE3")
    assert response.status_code in (200, 503, 504)
    if response.status_code == 200:
        data = response.json()
        assert "quotes" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_get_history(async_client: AsyncClient) -> None:
    """Verifica rota de histórico OHLCV."""
    response = await async_client.get("/api/quote/PETR4/history?range=1mo&interval=1d")
    assert response.status_code in (200, 503, 504)
