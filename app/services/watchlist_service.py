"""
Serviço de watchlists (favoritos).

Gerencia listas de ativos favoritos por usuário.
Multi-tenancy: toda operação filtra por user_id.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.repositories.local.models import (
    WatchlistItemModel,
    WatchlistModel,
    get_session,
)


class WatchlistService:
    """Serviço de gerenciamento de watchlists."""

    async def list_watchlists(self, user_id: str) -> list[dict[str, Any]]:
        """Lista todas as watchlists do usuário."""
        async with get_session() as session:
            result = await session.execute(
                select(WatchlistModel)
                .where(WatchlistModel.user_id == user_id)
                .options(selectinload(WatchlistModel.items))
            )
            watchlists = result.scalars().all()
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "item_count": len(w.items),
                    "created_at": w.created_at.isoformat(),
                }
                for w in watchlists
            ]

    async def create_watchlist(self, user_id: str, name: str) -> dict[str, Any]:
        """Cria uma nova watchlist."""
        async with get_session() as session:
            watchlist = WatchlistModel(user_id=user_id, name=name)
            session.add(watchlist)
            await session.commit()
            await session.refresh(watchlist)
            return {
                "id": watchlist.id,
                "name": watchlist.name,
                "item_count": 0,
                "created_at": watchlist.created_at.isoformat(),
            }

    async def rename_watchlist(
        self, user_id: str, watchlist_id: str, name: str
    ) -> dict[str, Any] | None:
        """Renomeia uma watchlist."""

        async with get_session() as session:
            result = await session.execute(
                select(WatchlistModel)
                .where(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .options(selectinload(WatchlistModel.items))
            )
            watchlist = result.scalars().first()
            if not watchlist:
                return None

            watchlist.name = name
            await session.commit()
            return {
                "id": watchlist.id,
                "name": watchlist.name,
                "item_count": len(watchlist.items),
                "created_at": watchlist.created_at.isoformat(),
            }

    async def delete_watchlist(self, user_id: str, watchlist_id: str) -> bool:
        """Remove uma watchlist (e todos os itens dela)."""

        async with get_session() as session:
            result = await session.execute(
                select(WatchlistModel).where(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
            )
            watchlist = result.scalars().first()
            if not watchlist:
                return False

            await session.delete(watchlist)
            await session.commit()
            return True

    async def list_items(
        self, user_id: str, watchlist_id: str
    ) -> list[dict[str, Any]] | None:
        """Lista os tickers de uma watchlist."""

        async with get_session() as session:
            result = await session.execute(
                select(WatchlistModel)
                .where(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .options(selectinload(WatchlistModel.items))
            )
            watchlist = result.scalars().first()
            if not watchlist:
                return None

            return [
                {
                    "id": item.id,
                    "ticker": item.ticker,
                    "notes": item.notes,
                    "added_at": item.added_at.isoformat(),
                }
                for item in watchlist.items
            ]

    async def add_item(
        self, user_id: str, watchlist_id: str, ticker: str, notes: str | None = None
    ) -> dict[str, Any] | None:
        """Adiciona um ticker a uma watchlist."""

        async with get_session() as session:
            result = await session.execute(
                select(WatchlistModel).where(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
            )
            watchlist = result.scalars().first()
            if not watchlist:
                return None

            item = WatchlistItemModel(
                watchlist_id=watchlist_id,
                ticker=ticker.upper(),
                notes=notes,
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return {
                "id": item.id,
                "ticker": item.ticker,
                "notes": item.notes,
                "added_at": item.added_at.isoformat(),
            }

    async def remove_item(self, user_id: str, watchlist_id: str, ticker: str) -> bool:
        """Remove um ticker de uma watchlist."""

        async with get_session() as session:
            watchlist_result = await session.execute(
                select(WatchlistModel).where(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
            )
            if not watchlist_result.scalars().first():
                return False

            item_result = await session.execute(
                select(WatchlistItemModel).where(
                    WatchlistItemModel.watchlist_id == watchlist_id,
                    WatchlistItemModel.ticker == ticker.upper(),
                )
            )
            item = item_result.scalars().first()
            if not item:
                return False

            await session.delete(item)
            await session.commit()
            return True
