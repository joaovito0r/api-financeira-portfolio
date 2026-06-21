"""
Rotas de listagem de ativos.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import rate_limit_data
from app.repositories.local.cache_repo import GenericCacheRepository
from app.schemas.asset import AssetListResponse
from app.services.asset_service import AssetService


def get_asset_service(request: Request) -> AssetService:
    return AssetService(
        brapi_client=request.app.state.brapi_client,
        cache_repo=GenericCacheRepository(),
    )


router = APIRouter(prefix="/api", tags=["Ativos"])


@router.get(
    "/assets",
    response_model=AssetListResponse,
    summary="Listar ativos disponíveis",
    description="Lista todos os ativos disponíveis com opção de filtro.",
    dependencies=[Depends(rate_limit_data)],
)
async def list_assets(
    search: str | None = Query(None, description="Busca por nome/ticker"),
    sector: str | None = Query(None, description="Filtrar por setor"),
    service: AssetService = Depends(get_asset_service),
) -> dict[str, Any]:
    """Lista ativos disponíveis na B3."""
    assets = await service.list_assets(search=search, sector=sector)
    return {"assets": assets, "total": len(assets)}


@router.get(
    "/available",
    summary="Lista simplificada de ativos",
    description="Versão leve da lista de ativos (apenas ticker, sem dados adicionais).",
    dependencies=[Depends(rate_limit_data)],
)
async def available(
    service: AssetService = Depends(get_asset_service),
) -> dict[str, Any]:
    """Lista simplificada de ativos."""
    symbols = await service.available()
    return {"symbols": symbols, "total": len(symbols)}
