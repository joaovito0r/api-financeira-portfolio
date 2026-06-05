"""
Rotas de consulta de dividendos.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.repositories.local.dividend_repo import LocalDividendRepository
from app.schemas.dividend import DividendListResponse
from app.services.dividend_service import DividendService


def get_dividend_service(request: Request) -> DividendService:
    return DividendService(
        brapi_client=request.app.state.brapi_client,
        local_repo=LocalDividendRepository(),
    )


router = APIRouter(prefix="/api", tags=["Dividendos"])


@router.get(
    "/dividends/{ticker}",
    response_model=DividendListResponse,
    summary="Dividendos de um ativo",
    description="Histórico de dividendos e proventos de um ativo.",
)
async def get_dividends(
    ticker: str,
    service: DividendService = Depends(get_dividend_service),
) -> dict:
    """Dividendos de um ativo específico."""
    dividends = await service.get_dividends(ticker.upper())
    return {"dividends": dividends, "total": len(dividends)}
