"""
Rotas de consulta de cotações.

Adaptado do projeto original do usuário com melhorias:
- Injeção de dependência
- Schemas Pydantic de resposta
- Cache integrado via service
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import (
    get_quote_service,
    rate_limit_data,
    rate_limit_expensive,
    valid_ticker,
)
from app.core.validation import normalize_ticker
from app.repositories.local.ohlcv_repo import LocalOHLCVRepository
from app.schemas.quote import QuoteListResponse, QuoteResponse
from app.services.historical_service import HistoricalService
from app.services.quote_service import QuoteService


def get_historical_service(request: Request) -> HistoricalService:
    return HistoricalService(
        brapi_client=request.app.state.brapi_client,
        local_repo=LocalOHLCVRepository(),
    )


router = APIRouter(prefix="/api", tags=["Cotações"])


@router.get(
    "/quote/{ticker}",
    response_model=QuoteResponse,
    summary="Cotação de um ativo",
    description="Retorna a cotação em tempo real de um ativo com cache de 15min.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_quote(
    ticker: str = Depends(valid_ticker),
    service: QuoteService = Depends(get_quote_service),
) -> dict[str, Any]:
    """Cotação de um ativo específico."""
    return await service.get_quote(ticker)


@router.get(
    "/quotes",
    response_model=QuoteListResponse,
    summary="Cotação de múltiplos ativos",
    description="Retorna cotações de vários ativos em uma requisição.",
    dependencies=[Depends(rate_limit_expensive)],
)
async def get_multiple_quotes(
    tickers: str = Query(..., description="Tickers separados por vírgula"),
    service: QuoteService = Depends(get_quote_service),
) -> dict[str, Any]:
    """Cotação de múltiplos ativos."""
    try:
        tickers_list = [
            normalize_ticker(t) for t in tickers.split(",") if t.strip()
        ]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    quotes = await service.get_multiple_quotes(tickers_list)
    return {"quotes": quotes, "total": len(quotes)}


@router.get(
    "/quote/{ticker}/history",
    summary="Histórico OHLCV",
    description="Histórico de preços de um ativo com cache perpétuo.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_history(
    ticker: str = Depends(valid_ticker),
    range: str = Query("1y", description="Período: 1d, 5d, 1mo, 6mo, 1y, 5y, max"),
    interval: str = Query("1d", description="Intervalo: 1d, 1wk, 1mo"),
    service: HistoricalService = Depends(get_historical_service),
) -> dict[str, Any]:
    """Histórico OHLCV de um ativo."""
    history = await service.get_history(ticker, range=range, interval=interval)
    return {"ticker": ticker, "history": history, "total": len(history)}
