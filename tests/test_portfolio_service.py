"""
Testes do serviço de carteira (posições).
"""

from __future__ import annotations

import uuid

import pytest

from app.repositories.local.models import UserModel, get_session
from app.services.portfolio_service import PortfolioService


@pytest.fixture
async def user_id() -> str:
    """Cria um usuário direto no banco e retorna o id."""
    async with get_session() as session:
        user = UserModel(
            name="Portfolio Service User",
            email=f"psvc_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


@pytest.mark.asyncio
async def test_add_and_list_position(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "PETR4", 100, 38.5)
    assert created["ticker"] == "PETR4"
    assert created["quantity"] == 100
    assert created["avg_cost"] == 38.5

    positions = await service.list_positions(user_id)
    tickers = [p["ticker"] for p in positions]
    assert "PETR4" in tickers


@pytest.mark.asyncio
async def test_list_positions_isolated_by_user(user_id: str) -> None:
    other_id = str(uuid.uuid4())
    service = PortfolioService()
    await service.add_position(user_id, "VALE3", 50, 60.0)
    other_positions = await service.list_positions(other_id)
    assert other_positions == []


@pytest.mark.asyncio
async def test_update_position(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "ITUB4", 10, 30.0)
    updated = await service.update_position(
        user_id, created["id"], quantity=20, avg_cost=32.0
    )
    assert updated is not None
    assert updated["quantity"] == 20
    assert updated["avg_cost"] == 32.0


@pytest.mark.asyncio
async def test_update_position_wrong_user_returns_none(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "BBAS3", 10, 20.0)
    result = await service.update_position(
        str(uuid.uuid4()), created["id"], quantity=99
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_position(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "WEGE3", 5, 40.0)
    deleted = await service.delete_position(user_id, created["id"])
    assert deleted is True

    positions = await service.list_positions(user_id)
    ids = [p["id"] for p in positions]
    assert created["id"] not in ids


@pytest.mark.asyncio
async def test_delete_position_not_found(user_id: str) -> None:
    service = PortfolioService()
    deleted = await service.delete_position(user_id, str(uuid.uuid4()))
    assert deleted is False
