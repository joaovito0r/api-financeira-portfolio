"""
Rotas de dados fundamentalistas.

Perfil da empresa, BP, DRE, indicadores e estatísticas.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import rate_limit_data, valid_ticker
from app.repositories.local.cache_repo import GenericCacheRepository
from app.services.fundamental_service import FundamentalService


def get_fundamental_service(request: Request) -> FundamentalService:
    return FundamentalService(
        brapi_client=request.app.state.brapi_client,
        cache_repo=GenericCacheRepository(),
    )


router = APIRouter(prefix="/api/quote/{ticker}", tags=["Fundamentalistas"])


@router.get(
    "/profile",
    summary="Perfil da empresa",
    description="Dados cadastrais e descrição da empresa.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_profile(
    ticker: str = Depends(valid_ticker),
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict[str, Any]:
    """Perfil da empresa."""
    return await service.get_profile(ticker)


@router.get(
    "/balance-sheet",
    summary="Balanço Patrimonial",
    description="BP: ativos, passivos e patrimônio líquido.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_balance_sheet(
    ticker: str = Depends(valid_ticker),
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict[str, Any]:
    """Balanço Patrimonial."""
    data = await service.get_balance_sheet(ticker)
    return {"ticker": ticker, "balance_sheets": data}


@router.get(
    "/income-statement",
    summary="DRE",
    description="Demonstrativo de Resultados: receita, lucro, EBITDA.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_income_statement(
    ticker: str = Depends(valid_ticker),
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict[str, Any]:
    """DRE."""
    data = await service.get_income_statement(ticker)
    return {"ticker": ticker, "income_statements": data}


@router.get(
    "/indicators",
    summary="Indicadores financeiros",
    description="ROE, ROA, margens, crescimento, dívida/PL.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_indicators(
    ticker: str = Depends(valid_ticker),
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict[str, Any]:
    """Indicadores financeiros."""
    return await service.get_indicators(ticker)


@router.get(
    "/statistics",
    summary="Estatísticas-chave",
    description="P/VP, P/L, EV/EBITDA, beta, DY, VPA, LPA.",
    dependencies=[Depends(rate_limit_data)],
)
async def get_statistics(
    ticker: str = Depends(valid_ticker),
    service: FundamentalService = Depends(get_fundamental_service),
) -> dict[str, Any]:
    """Estatísticas-chave."""
    return await service.get_statistics(ticker)
