"""
Rotas de watchlists (favoritos).

Todas as rotas exigem autenticação JWT.
O usuário só acessa suas próprias watchlists (multi-tenancy).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.core.validation import normalize_ticker
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/me/watchlists", tags=["Watchlists"])
service = WatchlistService()


@router.get("", summary="Listar watchlists")
async def list_watchlists(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Lista todas as watchlists do usuário logado."""
    watchlists = await service.list_watchlists(current_user["id"])
    return {"watchlists": watchlists, "total": len(watchlists)}


@router.post("", summary="Criar watchlist")
async def create_watchlist(
    name: str = Query(
        ..., min_length=1, max_length=100, description="Nome da watchlist"
    ),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Cria uma nova watchlist."""
    watchlist = await service.create_watchlist(current_user["id"], name)
    return watchlist


@router.patch("/{watchlist_id}", summary="Renomear watchlist")
async def rename_watchlist(
    watchlist_id: str,
    name: str = Query(..., min_length=1, max_length=100, description="Novo nome"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Renomeia uma watchlist existente."""
    result = await service.rename_watchlist(current_user["id"], watchlist_id, name)
    if not result:
        raise HTTPException(status_code=404, detail="Watchlist não encontrada")
    return result


@router.delete("/{watchlist_id}", summary="Remover watchlist")
async def delete_watchlist(
    watchlist_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Remove uma watchlist e todos os seus itens."""
    deleted = await service.delete_watchlist(current_user["id"], watchlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist não encontrada")
    return {"detail": "Watchlist removida com sucesso"}


@router.get("/{watchlist_id}/items", summary="Listar tickers da watchlist")
async def list_items(
    watchlist_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Lista os tickers salvos em uma watchlist."""
    items = await service.list_items(current_user["id"], watchlist_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Watchlist não encontrada")
    return {"items": items, "total": len(items)}


@router.post("/{watchlist_id}/items", summary="Adicionar ticker")
async def add_item(
    watchlist_id: str,
    ticker: str = Query(..., description="Ticker do ativo (ex: PETR4)"),
    notes: str | None = Query(None, description="Anotações opcionais"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Adiciona um ativo à watchlist."""
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    result = await service.add_item(current_user["id"], watchlist_id, ticker, notes)
    if not result:
        raise HTTPException(status_code=404, detail="Watchlist não encontrada")
    return result


@router.delete("/{watchlist_id}/items/{ticker}", summary="Remover ticker")
async def remove_item(
    watchlist_id: str,
    ticker: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Remove um ativo da watchlist."""
    removed = await service.remove_item(current_user["id"], watchlist_id, ticker)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail="Watchlist ou ticker não encontrado",
        )
    return {"detail": f"{ticker.upper()} removido da watchlist"}
