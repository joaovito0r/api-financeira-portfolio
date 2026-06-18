"""
Testes das rotas de watchlists.
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
            "name": "Watchlist User",
            "email": f"wl_user_{suffix}@example.com",
            "password": "senha_segura_123",
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_watchlist(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica criação de watchlist."""
    response = await async_client.post(
        "/me/watchlists?name=Minhas Ações",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Minhas Ações"
    assert data["item_count"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_list_watchlists(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica listagem de watchlists."""
    # Cria duas
    await async_client.post(
        "/me/watchlists?name=FIIs",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    await async_client.post(
        "/me/watchlists?name=Ações Internacionais",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = await async_client.get(
        "/me/watchlists",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    names = [wl["name"] for wl in data["watchlists"]]
    assert "FIIs" in names
    assert "Ações Internacionais" in names


@pytest.mark.asyncio
async def test_rename_watchlist(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica renomeação de watchlist."""
    # Cria
    created = await async_client.post(
        "/me/watchlists?name=Antigo",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    wl_id = created.json()["id"]

    # Renomeia
    response = await async_client.patch(
        f"/me/watchlists/{wl_id}?name=Novo+Nome",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Novo Nome"


@pytest.mark.asyncio
async def test_delete_watchlist(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica remoção de watchlist."""
    # Cria
    created = await async_client.post(
        "/me/watchlists?name=Temp",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    wl_id = created.json()["id"]

    # Deleta
    response = await async_client.delete(
        f"/me/watchlists/{wl_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200

    # Verifica que sumiu
    list_resp = await async_client.get(
        "/me/watchlists",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    ids = [wl["id"] for wl in list_resp.json()["watchlists"]]
    assert wl_id not in ids


@pytest.mark.asyncio
async def test_add_and_list_items(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica adicionar e listar tickers na watchlist."""
    # Cria watchlist
    created = await async_client.post(
        "/me/watchlists?name=Carteira",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    wl_id = created.json()["id"]

    # Adiciona tickers
    await async_client.post(
        f"/me/watchlists/{wl_id}/items?ticker=PETR4",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    await async_client.post(
        f"/me/watchlists/{wl_id}/items?ticker=VALE3&notes=Mineração",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Lista
    response = await async_client.get(
        f"/me/watchlists/{wl_id}/items",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    tickers = [item["ticker"] for item in data["items"]]
    assert "PETR4" in tickers
    assert "VALE3" in tickers


@pytest.mark.asyncio
async def test_remove_item(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica remoção de ticker da watchlist."""
    # Cria watchlist com item
    created = await async_client.post(
        "/me/watchlists?name=Teste",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    wl_id = created.json()["id"]

    await async_client.post(
        f"/me/watchlists/{wl_id}/items?ticker=BBAS3",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Remove
    response = await async_client.delete(
        f"/me/watchlists/{wl_id}/items/BBAS3",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200

    # Verifica que sumiu
    items_resp = await async_client.get(
        f"/me/watchlists/{wl_id}/items",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert items_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_watchlist_unauthorized(async_client: AsyncClient) -> None:
    """Verifica que rotas de watchlist sem token retornam 401."""
    response = await async_client.get("/me/watchlists")
    assert response.status_code == 401
    response = await async_client.post("/me/watchlists?name=Test")
    assert response.status_code == 401
