"""
Testes das rotas de carteira (portfolio).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth_token(async_client: AsyncClient) -> str:
    """Registra e retorna token de autenticação (email único por chamada)."""
    suffix = uuid.uuid4().hex[:8]
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Portfolio User",
            "email": f"pf_user_{suffix}@example.com",
            "password": "senha_segura_123",
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_add_position(async_client: AsyncClient, auth_token: str) -> None:
    response = await async_client.post(
        "/me/portfolio?ticker=PETR4&quantity=100&avg_cost=38.5",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "PETR4"
    assert data["quantity"] == 100
    assert data["avg_cost"] == 38.5
    assert "id" in data


@pytest.mark.asyncio
async def test_list_positions(async_client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    await async_client.post(
        "/me/portfolio?ticker=VALE3&quantity=50&avg_cost=60", headers=headers
    )
    await async_client.post(
        "/me/portfolio?ticker=ITUB4&quantity=80&avg_cost=30", headers=headers
    )
    response = await async_client.get("/me/portfolio", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    tickers = [p["ticker"] for p in data["positions"]]
    assert "VALE3" in tickers
    assert "ITUB4" in tickers


@pytest.mark.asyncio
async def test_update_position(async_client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    created = await async_client.post(
        "/me/portfolio?ticker=BBAS3&quantity=10&avg_cost=20", headers=headers
    )
    pos_id = created.json()["id"]
    response = await async_client.patch(
        f"/me/portfolio/{pos_id}?quantity=15&avg_cost=22", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 15
    assert data["avg_cost"] == 22


@pytest.mark.asyncio
async def test_delete_position(async_client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    created = await async_client.post(
        "/me/portfolio?ticker=WEGE3&quantity=5&avg_cost=40", headers=headers
    )
    pos_id = created.json()["id"]
    response = await async_client.delete(f"/me/portfolio/{pos_id}", headers=headers)
    assert response.status_code == 200

    list_resp = await async_client.get("/me/portfolio", headers=headers)
    ids = [p["id"] for p in list_resp.json()["positions"]]
    assert pos_id not in ids


@pytest.mark.asyncio
async def test_delete_position_not_found(
    async_client: AsyncClient, auth_token: str
) -> None:
    response = await async_client.delete(
        f"/me/portfolio/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_unauthorized(async_client: AsyncClient) -> None:
    response = await async_client.get("/me/portfolio")
    assert response.status_code == 401
    response = await async_client.post(
        "/me/portfolio?ticker=PETR4&quantity=1&avg_cost=1"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_add_position_invalid_ticker(
    async_client: AsyncClient, auth_token: str
) -> None:
    response = await async_client.post(
        "/me/portfolio?ticker=***&quantity=1&avg_cost=1",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422
