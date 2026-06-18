"""
Rota de relatório de ativos.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import rate_limit_expensive, valid_ticker
from app.services.report_service import ReportService

router = APIRouter(tags=["Relatórios"])


@router.get(
    "/reports/{ticker}",
    summary="Relatório completo do ativo",
    description=(
        "Gera um relatório completo com visão geral, performance, "
        "valuation, indicadores, saúde financeira e dividendos."
    ),
    dependencies=[Depends(rate_limit_expensive)],
)
async def get_report(
    request: Request, ticker: str = Depends(valid_ticker)
) -> dict[str, Any]:
    """Relatório completo de um ativo."""
    service = ReportService(brapi_client=request.app.state.brapi_client)
    return await service.generate_report(ticker)
