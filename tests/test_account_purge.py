"""Testes do job de purge definitivo de contas em soft delete."""

from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import select

from app.core import account_purge
from app.core.time_utils import utcnow_naive
from app.repositories.local.models import (
    AlertModel,
    PortfolioPositionModel,
    UserModel,
    WatchlistItemModel,
    WatchlistModel,
    get_session,
    init_db,
)


async def _create_user_with_data(deleted_at: datetime.datetime | None) -> str:
    """Cria um usuário com 1 watchlist+item, 1 alerta e 1 posição. Retorna o id."""
    async with get_session() as session:
        user = UserModel(
            name="Purge Test",
            email=f"purge_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
            deleted_at=deleted_at,
        )
        session.add(user)
        await session.flush()

        watchlist = WatchlistModel(user_id=user.id, name="Principal")
        session.add(watchlist)
        await session.flush()
        session.add(WatchlistItemModel(watchlist_id=watchlist.id, ticker="PETR4"))
        session.add(
            AlertModel(
                user_id=user.id, ticker="VALE3", target_price=10, direction="above"
            )
        )
        session.add(
            PortfolioPositionModel(
                user_id=user.id, ticker="ITUB4", quantity=10, avg_cost=20
            )
        )
        await session.commit()
        return user.id


@pytest.mark.asyncio
async def test_purge_removes_expired_account_and_cascades() -> None:
    await init_db()
    old_enough = utcnow_naive() - datetime.timedelta(days=31)
    user_id = await _create_user_with_data(deleted_at=old_enough)

    removed = await account_purge.purge_expired_accounts()
    assert removed == 1

    async with get_session() as session:
        assert (await session.get(UserModel, user_id)) is None
        watchlists = (
            (
                await session.execute(
                    select(WatchlistModel).where(WatchlistModel.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        alerts = (
            (
                await session.execute(
                    select(AlertModel).where(AlertModel.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        positions = (
            (
                await session.execute(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.user_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert watchlists == []
    assert alerts == []
    assert positions == []


@pytest.mark.asyncio
async def test_purge_keeps_account_within_window() -> None:
    await init_db()
    recent = utcnow_naive() - datetime.timedelta(days=5)
    user_id = await _create_user_with_data(deleted_at=recent)

    removed = await account_purge.purge_expired_accounts()
    assert removed == 0

    async with get_session() as session:
        assert (await session.get(UserModel, user_id)) is not None


@pytest.mark.asyncio
async def test_purge_keeps_active_account() -> None:
    await init_db()
    user_id = await _create_user_with_data(deleted_at=None)

    removed = await account_purge.purge_expired_accounts()
    assert removed == 0

    async with get_session() as session:
        assert (await session.get(UserModel, user_id)) is not None
