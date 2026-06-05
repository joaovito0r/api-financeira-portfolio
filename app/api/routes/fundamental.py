"""
Rotas de dados fundamentalistas.

Perfil da empresa, BP, DRE, indicadores e estatísticas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.services.fundamental_service import FundamentalService


def get_fundamental_service(request: Request) -> FundamentalService:
    return FundamentalService(brapi_client=request.app.state.brapi_client)


router = APIRouter(prefix="/api/quote/{ticker}", tags=["Fundamentalistas"])


@router.get(
    "/profile",
    summary="Perfil da empresa",
    description="Dados cadastrais e descrição da empresa.",
)
async def get_profile(
    ticker: str,
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict:
    """Perfil da empresa."""
    return await service.get_profile(ticker.upper())


@router.get(
    "/balance-sheet",
    summary="Balanço Patrimonial",
    description="BP: ativos, passivos e patrimônio líquido.",
)
async def get_balance_sheet(
    ticker: str,
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict:
    """Balanço Patrimonial."""
    data = await service.get_balance_sheet(ticker.upper())
    return {"ticker": ticker.upper(), "balance_sheets": data}


@router.get(
    "/income-statement",
    summary="DRE",
    description="Demonstrativo de Resultados: receita, lucro, EBITDA.",
)
async def get_income_statement(
    ticker: str,
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict:
    """DRE."""
    data = await service.get_income_statement(ticker.upper())
    return {"ticker": ticker.upper(), "income_statements": data}


@router.get(
    "/indicators",
    summary="Indicadores financeiros",
    description="ROE, ROA, margens, crescimento, dívida/PL.",
)
async def get_indicators(
    ticker: str,
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict:
    """Indicadores financeiros."""
    return await service.get_indicators(ticker.upper())


@router.get(
    "/statistics",
    summary="Estatísticas-chave",
    description="P/VP, P/L, EV/EBITDA, beta, DY, VPA, LPA.",
)
async def get_statistics(
    ticker: str,
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict:
    """Estatísticas-chave."""
    return await service.get_statistics(ticker.upper())
