"""Testes da conta demo: seed idempotente, guards de senha/exclusão e reset."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import settings
from app.core import demo_seed
from app.core.demo_data import DEMO_ALERTS, DEMO_NAME, DEMO_PORTFOLIO, DEMO_WATCHLISTS
from app.repositories.local.models import (
    AlertModel,
    PortfolioPositionModel,
    UserModel,
    WatchlistItemModel,
    WatchlistModel,
    get_session,
    init_db,
)
from app.services.auth_service import AuthService


async def _get_demo_user() -> UserModel:
    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == settings.demo_account_email)
        )
        user = result.scalars().first()
        assert user is not None
        return user


@pytest.mark.asyncio
async def test_ensure_demo_user_creates_once() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()
    user = await _get_demo_user()
    assert user.is_demo is True
    assert user.name == DEMO_NAME

    # Chamar de novo não duplica a conta.
    await demo_seed.ensure_demo_user()
    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == settings.demo_account_email)
        )
        assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_reset_demo_data_populates_seed() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()
    ok = await demo_seed.reset_demo_data()
    assert ok is True

    user = await _get_demo_user()
    async with get_session() as session:
        positions = (
            (
                await session.execute(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        watchlists = (
            (
                await session.execute(
                    select(WatchlistModel).where(WatchlistModel.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        alerts = (
            (
                await session.execute(
                    select(AlertModel).where(AlertModel.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )

    assert len(positions) == len(DEMO_PORTFOLIO)
    assert len(watchlists) == len(DEMO_WATCHLISTS)
    assert len(alerts) == len(DEMO_ALERTS)


@pytest.mark.asyncio
async def test_reset_demo_data_wipes_visitor_changes() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()
    await demo_seed.reset_demo_data()
    user = await _get_demo_user()

    # Simula um visitante mexendo na conta: renomeia, adiciona posição e lista.
    async with get_session() as session:
        db_user = await session.get(UserModel, user.id)
        assert db_user is not None
        db_user.name = "Nome bagunçado pelo visitante"
        session.add(
            PortfolioPositionModel(
                user_id=user.id, ticker="AAPL34", quantity=999, avg_cost=1.0
            )
        )
        session.add(WatchlistModel(user_id=user.id, name="Lixo do visitante"))
        await session.commit()

    ok = await demo_seed.reset_demo_data()
    assert ok is True

    user_after = await _get_demo_user()
    assert user_after.name == DEMO_NAME
    async with get_session() as session:
        positions = (
            (
                await session.execute(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        watchlists = (
            (
                await session.execute(
                    select(WatchlistModel).where(WatchlistModel.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
    tickers = {p.ticker for p in positions}
    assert "AAPL34" not in tickers
    assert len(positions) == len(DEMO_PORTFOLIO)
    names = {w.name for w in watchlists}
    assert "Lixo do visitante" not in names


@pytest.mark.asyncio
async def test_reset_demo_data_returns_false_when_no_demo_user() -> None:
    await init_db()
    # O banco de testes é compartilhado entre os testes do módulo (ver
    # conftest.py) — remove a conta demo que outros testes possam ter criado
    # para simular o cenário de "ainda não existe".
    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == settings.demo_account_email)
        )
        existing = result.scalars().first()
        if existing is not None:
            await session.delete(existing)
            await session.commit()

    ok = await demo_seed.reset_demo_data()
    assert ok is False


@pytest.mark.asyncio
async def test_demo_watchlist_items_cascade_on_reset() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()
    await demo_seed.reset_demo_data()
    user = await _get_demo_user()

    async with get_session() as session:
        watchlists_before = (
            (
                await session.execute(
                    select(WatchlistModel).where(WatchlistModel.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
    wl_ids_before = [w.id for w in watchlists_before]

    await demo_seed.reset_demo_data()

    async with get_session() as session:
        # Itens das watchlists antigas não devem sobrar órfãos.
        orphan_items = (
            (
                await session.execute(
                    select(WatchlistItemModel).where(
                        WatchlistItemModel.watchlist_id.in_(wl_ids_before)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert orphan_items == []


@pytest.mark.asyncio
async def test_change_password_blocked_for_demo_account() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()
    user = await _get_demo_user()

    service = AuthService()
    with pytest.raises(ValueError, match="conta demo"):
        await service.change_password(
            user.id, settings.demo_account_password, "OutraSenha@123"
        )


@pytest.mark.asyncio
async def test_delete_account_blocked_for_demo_account() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()
    user = await _get_demo_user()

    service = AuthService()
    with pytest.raises(ValueError, match="conta demo"):
        await service.request_deletion(user.id, settings.demo_account_password)


@pytest.mark.asyncio
async def test_demo_login_reports_is_demo_flag() -> None:
    await init_db()
    await demo_seed.ensure_demo_user()

    service = AuthService()
    result = await service.login(
        settings.demo_account_email, settings.demo_account_password
    )
    assert result["user"]["is_demo"] is True
