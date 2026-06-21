"""Testes do fluxo de exclusão de conta (soft delete + janela de recuperação)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

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


@pytest.mark.asyncio
async def test_delete_account_wrong_password(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Senha errada não marca a conta para exclusão."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Del Wrong",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_errada"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400

    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == unique_email.lower())
        )
        user = result.scalars().first()
    assert user is not None
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_delete_account_success(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Senha certa marca deleted_at e devolve a data-limite."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Del Ok",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_correta_123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "purge_at" in response.json()

    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == unique_email.lower())
        )
        user = result.scalars().first()
    assert user is not None
    assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_request_deletion_twice_does_not_reset_clock() -> None:
    """Chamar a exclusão de novo numa conta já em limbo não reseta `deleted_at`.

    Testado direto no service (não via HTTP) porque, depois da Task 3, uma
    segunda chamada autenticada nem chegaria no service — o token já seria
    rejeitado em `get_current_user`. Este teste verifica a regra de negócio
    isoladamente, sem depender da ordem das tasks.
    """
    from app.core.security import hash_password
    from app.services.auth_service import AuthService

    async with get_session() as session:
        user = UserModel(
            name="Del Twice Direct",
            email=f"del_twice_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("senha_correta_123"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    service = AuthService()
    await service.request_deletion(user_id, "senha_correta_123")

    with pytest.raises(ValueError, match="já está marcada"):
        await service.request_deletion(user_id, "senha_correta_123")


@pytest.mark.asyncio
async def test_token_rejected_after_deletion(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Token emitido antes da exclusão deixa de funcionar em rotas autenticadas."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Bloqueio",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    delete_resp = await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_correta_123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 200

    me = await async_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_login_reactivates_account(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Login com sucesso dentro da janela reativa a conta automaticamente."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Reativa",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_correta_123"},
        headers={"Authorization": f"Bearer {token}"},
    )

    login = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_correta_123"},
    )
    assert login.status_code == 200
    data = login.json()
    assert data["reactivated"] is True
    new_token = data["access_token"]

    me = await async_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert me.status_code == 200

    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == unique_email.lower())
        )
        user = result.scalars().first()
    assert user is not None
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_login_normal_has_no_reactivated_flag(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Login normal (conta nunca excluída) não deve trazer reactivated=True."""
    await async_client.post(
        "/auth/register",
        json={
            "name": "Normal",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    login = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_correta_123"},
    )
    assert login.status_code == 200
    assert login.json()["reactivated"] is False
