"""
Rota de relatório de ativos.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.services.report_service import ReportService

router = APIRouter(tags=["Relatórios"])


@router.get(
    "/reports/{ticker}",
    summary="Relatório completo do ativo",
    description=(
        "Gera um relatório completo com visão geral, performance, "
        "valuation, indicadores, saúde financeira e dividendos."
    ),
)
async def get_report(ticker: str, request: Request) -> dict:
    """Relatório completo de um ativo."""
    service = ReportService(brapi_client=request.app.state.brapi_client)
    return await service.generate_report(ticker.upper())
