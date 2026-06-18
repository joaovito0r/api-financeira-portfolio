"""
Testes das rotas de autenticação.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
def unique_email() -> str:
    """Gera email único para cada teste evitar colisão no banco persistido."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_register(async_client: AsyncClient, unique_email: str) -> None:
    """Verifica registro de novo usuário."""
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Test User",
            "email": unique_email,
            "password": "senha_segura_123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["name"] == "Test User"
    assert data["user"]["email"] == unique_email


@pytest.mark.asyncio
async def test_register_duplicate_email(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Verifica que email duplicado retorna 400."""
    # Primeiro registro
    await async_client.post(
        "/auth/register",
        json={
            "name": "First",
            "email": unique_email,
            "password": "senha_segura_123",
        },
    )
    # Segundo com mesmo email
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Second",
            "email": unique_email,
            "password": "outra_senha_456",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "já cadastrado" in data["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email(async_client: AsyncClient) -> None:
    """Verifica que email inválido retorna 422."""
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Test",
            "email": "invalido",
            "password": "senha_segura_123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(async_client: AsyncClient) -> None:
    """Verifica que senha curta retorna 422."""
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Test",
            "email": "unique_short@example.com",
            "password": "123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login(async_client: AsyncClient, unique_email: str) -> None:
    """Verifica login com credenciais corretas."""
    # Primeiro registra
    await async_client.post(
        "/auth/register",
        json={
            "name": "Login Test",
            "email": unique_email,
            "password": "senha_segura_123",
        },
    )
    # Depois faz login
    response = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_segura_123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Verifica que senha errada retorna 401."""
    await async_client.post(
        "/auth/register",
        json={
            "name": "Wrong Pass",
            "email": unique_email,
            "password": "senha_segura_123",
        },
    )
    response = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_errada"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(async_client: AsyncClient, unique_email: str) -> None:
    """Verifica rota /auth/me com token válido."""
    # Registra e pega o token
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Me Test",
            "email": unique_email,
            "password": "senha_segura_123",
        },
    )
    token = reg.json()["access_token"]

    # Acessa /me
    response = await async_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Me Test"
    assert data["email"] == unique_email


@pytest.mark.asyncio
async def test_get_me_unauthorized(async_client: AsyncClient) -> None:
    """Verifica que /auth/me sem token retorna 401."""
    response = await async_client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(async_client: AsyncClient) -> None:
    """Verifica que /auth/me com token inválido retorna 401."""
    response = await async_client.get(
        "/auth/me", headers={"Authorization": "Bearer token_invalido_aqui"}
    )
    assert response.status_code == 401
