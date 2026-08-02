"""
Testes de DividendService + LocalDividendRepository: cache-first, conversão
do formato da brapi.dev e persistência local.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.repositories.local.dividend_repo import LocalDividendRepository
from app.services.dividend_service import DividendService


@pytest.mark.asyncio
async def test_get_dividends_cache_miss_fetches_and_saves() -> None:
    """Sem cache local: busca na brapi, converte e persiste."""
    brapi = AsyncMock()
    brapi.dividends = AsyncMock(
        return_value={
            "results": [
                {
                    "dividendsData": {
                        "cashDividends": [
                            {
                                "paymentDate": "2026-03-15T00:00:00.000Z",
                                "rate": 1.5,
                                "label": "RENDIMENTO",
                                "lastDatePrior": "2026-03-01T00:00:00.000Z",
                            },
                            {
                                "paymentDate": "2026-06-10T00:00:00.000Z",
                                "rate": 0.8,
                                "label": "JUROS",
                            },
                        ]
                    }
                }
            ]
        }
    )
    local = LocalDividendRepository()
    service = DividendService(brapi_client=brapi, local_repo=local)

    result = await service.get_dividends("divx4")

    assert len(result) == 2
    assert result[0]["value"] == 1.5
    assert result[0]["type"] == "DIVIDENDO"
    assert result[0]["reference_date"] == "2026-03-01"
    assert result[1]["type"] == "JCP"
    assert result[1]["reference_date"] is None
    brapi.dividends.assert_awaited_once()

    # Segunda chamada: deve vir do cache local, sem tocar a brapi de novo.
    brapi.dividends.reset_mock()
    cached = await service.get_dividends("DIVX4")
    assert len(cached) == 2
    brapi.dividends.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_dividends_no_cash_dividends_returns_empty() -> None:
    """Quando a brapi não retorna cashDividends, retorna lista vazia."""
    brapi = AsyncMock()
    brapi.dividends = AsyncMock(
        return_value={"results": [{"dividendsData": {"cashDividends": []}}]}
    )
    local = LocalDividendRepository()
    service = DividendService(brapi_client=brapi, local_repo=local)

    result = await service.get_dividends("SEMDIV3")
    assert result == []


def test_map_label_unknown_passthrough() -> None:
    """Label desconhecida passa direto (sem mapeamento)."""
    service = DividendService(brapi_client=AsyncMock(), local_repo=AsyncMock())
    assert service._map_label("OUTRO") == "OUTRO"
    assert service._map_label("bonificacao") == "BONIFICACAO"


@pytest.mark.asyncio
async def test_local_repo_get_returns_none_when_empty() -> None:
    repo = LocalDividendRepository()
    result = await repo.get("NAOEXISTE3")
    assert result is None


@pytest.mark.asyncio
async def test_local_repo_save_skips_items_without_valid_date() -> None:
    repo = LocalDividendRepository()
    saved = await repo.save(
        "SKIP3",
        [
            {"payment_date": "", "value": 1.0, "type": "DIVIDENDO"},
            {"payment_date": "2026-01-10", "value": 2.0, "type": "DIVIDENDO"},
        ],
    )
    assert len(saved) == 1
    assert saved[0]["payment_date"] == "2026-01-10"
