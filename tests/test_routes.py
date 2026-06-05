"""
Testes das rotas de dividendos e ativos.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_dividends(async_client: AsyncClient) -> None:
    """Verifica rota de dividendos."""
    response = await async_client.get("/api/dividends/PETR4")
    assert response.status_code in (200, 503, 504)
    if response.status_code == 200:
        data = response.json()
        assert "dividends" in data


@pytest.mark.asyncio
async def test_list_assets(async_client: AsyncClient) -> None:
    """Verifica rota de listagem de ativos."""
    response = await async_client.get("/api/assets")
    assert response.status_code in (200, 503, 504)
    if response.status_code == 200:
        data = response.json()
        assert "assets" in data


@pytest.mark.asyncio
async def test_available(async_client: AsyncClient) -> None:
    """Verifica rota de lista simplificada."""
    response = await async_client.get("/api/available")
    assert response.status_code in (200, 503, 504)


@pytest.mark.asyncio
async def test_fundamental_routes(async_client: AsyncClient) -> None:
    """Verifica se as rotas fundamentalistas respondem."""
    for path in [
        "/api/quote/PETR4/profile",
        "/api/quote/PETR4/balance-sheet",
        "/api/quote/PETR4/income-statement",
        "/api/quote/PETR4/indicators",
        "/api/quote/PETR4/statistics",
    ]:
        response = await async_client.get(path)
        # Podem retornar 200, 503 (brapi offline) ou 504 (timeout)
        assert response.status_code in (200, 503, 504), f"{path} failed"
