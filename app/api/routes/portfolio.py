"""
Rotas de carteira (posições de ativos do usuário).

Todas as rotas exigem autenticação JWT.
O usuário só acessa suas próprias posições (multi-tenancy).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import rate_limit_user
from app.core.validation import normalize_ticker
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/me/portfolio", tags=["Carteira"])
service = PortfolioService()


@router.get("", summary="Listar posições da carteira")
async def list_positions(
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Lista todas as posições da carteira do usuário logado."""
    positions = await service.list_positions(current_user["id"])
    return {"positions": positions, "total": len(positions)}


@router.post("", summary="Adicionar posição")
async def add_position(
    ticker: str = Query(..., description="Ticker do ativo (ex: PETR4)"),
    quantity: int = Query(..., gt=0, description="Quantidade de ações"),
    avg_cost: float = Query(..., gt=0, description="Preço médio de compra"),
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Adiciona um ativo à carteira."""
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return await service.add_position(current_user["id"], ticker, quantity, avg_cost)


@router.patch("/{position_id}", summary="Atualizar posição")
async def update_position(
    position_id: str,
    quantity: int | None = Query(None, gt=0),
    avg_cost: float | None = Query(None, gt=0),
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Atualiza quantidade e/ou custo médio de uma posição."""
    result = await service.update_position(
        current_user["id"], position_id, quantity=quantity, avg_cost=avg_cost
    )
    if not result:
        raise HTTPException(status_code=404, detail="Posição não encontrada")
    return result


@router.delete("/{position_id}", summary="Remover posição")
async def delete_position(
    position_id: str,
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Remove uma posição da carteira."""
    deleted = await service.delete_position(current_user["id"], position_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Posição não encontrada")
    return {"detail": "Posição removida com sucesso"}
