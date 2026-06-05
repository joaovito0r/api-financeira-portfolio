"""
Serviço de watchlists (favoritos).

Gerencia listas de ativos favoritos por usuário.
Multi-tenancy: toda operação filtra por user_id.
"""

from __future__ import annotations

from app.repositories.local.models import (
    WatchlistItemModel,
    WatchlistModel,
    get_session,
)


class WatchlistService:
    """Serviço de gerenciamento de watchlists."""

    async def list_watchlists(self, user_id: str) -> list[dict]:
        """Lista todas as watchlists do usuário."""
        with get_session() as session:
            watchlists = (
                session.query(WatchlistModel)
                .filter(WatchlistModel.user_id == user_id)
                .all()
            )
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "item_count": len(w.items),
                    "created_at": w.created_at.isoformat(),
                }
                for w in watchlists
            ]

    async def create_watchlist(self, user_id: str, name: str) -> dict:
        """Cria uma nova watchlist."""
        with get_session() as session:
            watchlist = WatchlistModel(user_id=user_id, name=name)
            session.add(watchlist)
            session.commit()
            session.refresh(watchlist)
            return {
                "id": watchlist.id,
                "name": watchlist.name,
                "item_count": 0,
                "created_at": watchlist.created_at.isoformat(),
            }

    async def rename_watchlist(
        self, user_id: str, watchlist_id: str, name: str
    ) -> dict | None:
        """Renomeia uma watchlist."""
        with get_session() as session:
            watchlist = (
                session.query(WatchlistModel)
                .filter(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .first()
            )
            if not watchlist:
                return None

            watchlist.name = name
            session.commit()
            return {
                "id": watchlist.id,
                "name": watchlist.name,
                "item_count": len(watchlist.items),
                "created_at": watchlist.created_at.isoformat(),
            }

    async def delete_watchlist(
        self, user_id: str, watchlist_id: str
    ) -> bool:
        """Remove uma watchlist (e todos os itens dela)."""
        with get_session() as session:
            watchlist = (
                session.query(WatchlistModel)
                .filter(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .first()
            )
            if not watchlist:
                return False

            session.delete(watchlist)
            session.commit()
            return True

    async def list_items(self, user_id: str, watchlist_id: str) -> list[dict] | None:
        """Lista os tickers de uma watchlist."""
        with get_session() as session:
            watchlist = (
                session.query(WatchlistModel)
                .filter(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .first()
            )
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
    ) -> dict | None:
        """Adiciona um ticker a uma watchlist."""
        with get_session() as session:
            watchlist = (
                session.query(WatchlistModel)
                .filter(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .first()
            )
            if not watchlist:
                return None

            item = WatchlistItemModel(
                watchlist_id=watchlist_id,
                ticker=ticker.upper(),
                notes=notes,
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return {
                "id": item.id,
                "ticker": item.ticker,
                "notes": item.notes,
                "added_at": item.added_at.isoformat(),
            }

    async def remove_item(
        self, user_id: str, watchlist_id: str, ticker: str
    ) -> bool:
        """Remove um ticker de uma watchlist."""
        with get_session() as session:
            watchlist = (
                session.query(WatchlistModel)
                .filter(
                    WatchlistModel.id == watchlist_id,
                    WatchlistModel.user_id == user_id,
                )
                .first()
            )
            if not watchlist:
                return False

            item = (
                session.query(WatchlistItemModel)
                .filter(
                    WatchlistItemModel.watchlist_id == watchlist_id,
                    WatchlistItemModel.ticker == ticker.upper(),
                )
                .first()
            )
            if not item:
                return False

            session.delete(item)
            session.commit()
            return True
