"""
Testes da rota de comparação de ativos (/compare).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture(autouse=True)
def reset_brapi_quote():
    """Restaura o mock padrão de quote() após cada teste desta suíte."""
    original = app.state.brapi_client.quote
    yield
    app.state.brapi_client.quote = original


@pytest.mark.asyncio
async def test_compare_two_tickers(async_client: AsyncClient) -> None:
    """Verifica comparação de dois ativos com métricas completas."""

    async def fake_quote(ticker: str, modules: str | None = None) -> dict:
        if modules == "financialData":
            return {
                "results": [
                    {
                        "financialData": {
                            "returnOnEquity": 0.2,
                            "returnOnAssets": 0.1,
                            "profitMargins": 0.15,
                            "targetMeanPrice": 45.0,
                            "recommendationKey": "buy",
                        }
                    }
                ]
            }
        if modules == "defaultKeyStatistics":
            return {
                "results": [
                    {
                        "defaultKeyStatistics": {
                            "trailingPE": 8.5,
                            "priceToBook": 1.2,
                            "enterpriseToEbitda": 5.0,
                            "dividendYield": 0.08,
                            "beta": 0.9,
                            "bookValue": 20.0,
                            "earningsPerShare": 3.5,
                        }
                    }
                ]
            }
        if modules == "summaryProfile":
            return {
                "results": [{"summaryProfile": {"sector": "Energy", "industry": "Oil"}}]
            }
        return {
            "results": [
                {
                    "longName": f"{ticker} S.A.",
                    "regularMarketPrice": 38.0,
                    "regularMarketChangePercent": 1.5,
                    "marketCap": 500_000_000,
                }
            ]
        }

    app.state.brapi_client.quote = AsyncMock(side_effect=fake_quote)

    response = await async_client.get("/compare?tickers=PETR4,VALE3")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    tickers = {r["ticker"] for r in data["tickers"]}
    assert tickers == {"PETR4", "VALE3"}
    petr4 = next(r for r in data["tickers"] if r["ticker"] == "PETR4")
    assert petr4["price"] == 38.0
    assert petr4["sector"] == "Energy"
    assert petr4["pl"] == 8.5
    assert petr4["roe"] == 0.2


@pytest.mark.asyncio
async def test_compare_requires_at_least_two_tickers(
    async_client: AsyncClient,
) -> None:
    """Verifica que um único ticker retorna 400."""
    response = await async_client.get("/compare?tickers=PETR4")
    assert response.status_code == 400
    assert "pelo menos 2" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_invalid_ticker(async_client: AsyncClient) -> None:
    """Verifica que ticker inválido retorna 422."""
    response = await async_client.get("/compare?tickers=PETR4,***")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_compare_ignores_empty_entries(async_client: AsyncClient) -> None:
    """Verifica que entradas vazias entre vírgulas são ignoradas."""
    response = await async_client.get("/compare?tickers=PETR4,,VALE3,")
    assert response.status_code == 200
    assert response.json()["total"] == 2
