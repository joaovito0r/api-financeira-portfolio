"""Testes do fluxo de exclusão de conta (soft delete + janela de recuperação)."""

from __future__ import annotations

import uuid

import pytest

from app.repositories.local.models import UserModel, get_session


@pytest.fixture
def unique_email() -> str:
    """Gera email único para cada teste evitar colisão no banco persistido."""
    return f"del_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_user_model_has_deletion_fields() -> None:
    """`deleted_at` existe e é nulo por padrão; relações de cascade existem."""
    async with get_session() as session:
        user = UserModel(
            name="Modelo Teste",
            email=f"modelo_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    assert user.deleted_at is None
    relationship_names = set(UserModel.__mapper__.relationships.keys())
    assert {"alerts", "portfolio_positions", "watchlists"} <= relationship_names
