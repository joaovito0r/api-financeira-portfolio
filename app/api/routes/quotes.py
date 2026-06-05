"""
Rotas de consulta de cotações.

Adaptado do projeto original do usuário com melhorias:
- Injeção de dependência
- Schemas Pydantic de resposta
- Cache integrado via service
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.repositories.local.ohlcv_repo import LocalOHLCVRepository
from app.repositories.local.quote_repo import LocalQuoteRepository
from app.schemas.quote import QuoteListResponse, QuoteResponse
from app.services.historical_service import HistoricalService
from app.services.quote_service import QuoteService


def get_quote_service(request: Request) -> QuoteService:
    return QuoteService(
        brapi_client=request.app.state.brapi_client,
        local_repo=LocalQuoteRepository(),
    )


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
)
async def get_quote(
    ticker: str,
    service: QuoteService = Depends(get_quote_service),
) -> dict:
    """Cotação de um ativo específico."""
    return await service.get_quote(ticker.upper())


@router.get(
    "/quotes",
    response_model=QuoteListResponse,
    summary="Cotação de múltiplos ativos",
    description="Retorna cotações de vários ativos em uma requisição.",
)
async def get_multiple_quotes(
    tickers: str = Query(..., description="Tickers separados por vírgula"),
    service: QuoteService = Depends(get_quote_service),
) -> dict:
    """Cotação de múltiplos ativos."""
    tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
    quotes = await service.get_multiple_quotes(tickers_list)
    return {"quotes": quotes, "total": len(quotes)}


@router.get(
    "/quote/{ticker}/history",
    summary="Histórico OHLCV",
    description="Histórico de preços de um ativo com cache perpétuo.",
)
async def get_history(
    ticker: str,
    range: str = Query("1y", description="Período: 1d, 5d, 1mo, 6mo, 1y, 5y, max"),
    interval: str = Query("1d", description="Intervalo: 1d, 1wk, 1mo"),
    service: HistoricalService = Depends(get_historical_service),
) -> dict:
    """Histórico OHLCV de um ativo."""
    history = await service.get_history(ticker.upper(), range=range, interval=interval)
    return {"ticker": ticker.upper(), "history": history, "total": len(history)}
