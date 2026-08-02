"""
Testes das rotas de alertas de preço.

Cobre criação, listagem, remoção e verificação (disparo above/below,
preço indisponível, verificação em lote) — funcionalidade central do produto.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
async def auth_token(async_client: AsyncClient) -> str:
    """Registra e retorna token de autenticação (email único por chamada)."""
    suffix = uuid.uuid4().hex[:8]
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Alert User",
            "email": f"alert_user_{suffix}@example.com",
            "password": "senha_segura_123",
        },
    )
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def reset_brapi_quote():
    """Restaura o mock padrão de quote() após cada teste desta suíte."""
    original = app.state.brapi_client.quote
    yield
    app.state.brapi_client.quote = original


@pytest.mark.asyncio
async def test_create_alert(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica criação de alerta de preço."""
    response = await async_client.post(
        "/me/alerts?ticker=PETR4&target_price=40.5&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "PETR4"
    assert data["target_price"] == 40.5
    assert data["direction"] == "above"
    assert data["triggered"] is False


@pytest.mark.asyncio
async def test_create_alert_invalid_ticker(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que ticker inválido retorna 422."""
    response = await async_client.post(
        "/me/alerts?ticker=***&target_price=40&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_alert_invalid_direction(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que direção inválida retorna 400."""
    response = await async_client.post(
        "/me/alerts?ticker=PETR4&target_price=40&direction=sideways",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400
    assert "Direção inválida" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_alert_invalid_price(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que preço alvo <= 0 retorna 400."""
    response = await async_client.post(
        "/me/alerts?ticker=PETR4&target_price=0&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400
    assert "maior que zero" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_alerts(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica listagem de alertas do usuário."""
    await async_client.post(
        "/me/alerts?ticker=VALE3&target_price=60&direction=below",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    response = await async_client.get(
        "/me/alerts",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(a["ticker"] == "VALE3" for a in data["alerts"])


@pytest.mark.asyncio
async def test_delete_alert(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica remoção de alerta."""
    create = await async_client.post(
        "/me/alerts?ticker=ITUB4&target_price=30&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    alert_id = create.json()["id"]

    response = await async_client.delete(
        f"/me/alerts/{alert_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200

    check = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert check.status_code == 404


@pytest.mark.asyncio
async def test_delete_alert_not_found(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que remover alerta inexistente retorna 404."""
    response = await async_client.delete(
        "/me/alerts/id-que-nao-existe",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_check_alert_not_found(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que checar alerta inexistente retorna 404."""
    response = await async_client.get(
        "/me/alerts/id-que-nao-existe/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_check_alert_triggers_above(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que alerta 'above' dispara quando preço atinge o alvo."""
    create = await async_client.post(
        "/me/alerts?ticker=PETR4&target_price=30&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    alert_id = create.json()["id"]

    app.state.brapi_client.quote = AsyncMock(
        return_value={"results": [{"regularMarketPrice": 35.0}]}
    )

    response = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["triggered"] is True
    assert data["current_price"] == 35.0

    # Segunda checagem: já disparado, não deve disparar de novo (idempotente).
    response2 = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response2.status_code == 200
    assert response2.json()["triggered"] is True


@pytest.mark.asyncio
async def test_check_alert_triggers_below(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica que alerta 'below' dispara quando preço cai abaixo do alvo."""
    create = await async_client.post(
        "/me/alerts?ticker=VALE3&target_price=60&direction=below",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    alert_id = create.json()["id"]

    app.state.brapi_client.quote = AsyncMock(
        return_value={"results": [{"regularMarketPrice": 55.0}]}
    )

    response = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["triggered"] is True
    assert data["current_price"] == 55.0


@pytest.mark.asyncio
async def test_check_alert_not_yet_triggered(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica alerta que ainda não atingiu o alvo."""
    create = await async_client.post(
        "/me/alerts?ticker=ITUB4&target_price=100&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    alert_id = create.json()["id"]

    app.state.brapi_client.quote = AsyncMock(
        return_value={"results": [{"regularMarketPrice": 30.0}]}
    )

    response = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["triggered"] is False
    assert "ainda não atingido" in data["message"]


@pytest.mark.asyncio
async def test_check_alert_price_unavailable(
    async_client: AsyncClient, auth_token: str
) -> None:
    """Verifica alerta quando a brapi não retorna preço."""
    create = await async_client.post(
        "/me/alerts?ticker=BBAS3&target_price=25&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    alert_id = create.json()["id"]

    app.state.brapi_client.quote = AsyncMock(return_value={"results": [{}]})

    response = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_price"] is None
    assert "Não foi possível obter" in data["message"]


@pytest.mark.asyncio
async def test_check_all_alerts(async_client: AsyncClient, auth_token: str) -> None:
    """Verifica checagem em lote: só retorna alertas não disparados."""
    await async_client.post(
        "/me/alerts?ticker=PETR4&target_price=10&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    await async_client.post(
        "/me/alerts?ticker=VALE3&target_price=10&direction=above",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    app.state.brapi_client.quote = AsyncMock(
        return_value={"results": [{"regularMarketPrice": 50.0}]}
    )

    response = await async_client.get(
        "/me/alerts/check-all",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert all(r["triggered"] for r in data["results"])


@pytest.mark.asyncio
async def test_alerts_multi_tenancy(async_client: AsyncClient) -> None:
    """Verifica que um usuário não acessa alertas de outro."""
    user_a = await async_client.post(
        "/auth/register",
        json={
            "name": "User A",
            "email": f"alert_a_{uuid.uuid4().hex[:8]}@example.com",
            "password": "senha_segura_123",
        },
    )
    user_b = await async_client.post(
        "/auth/register",
        json={
            "name": "User B",
            "email": f"alert_b_{uuid.uuid4().hex[:8]}@example.com",
            "password": "senha_segura_123",
        },
    )
    token_a = user_a.json()["access_token"]
    token_b = user_b.json()["access_token"]

    create = await async_client.post(
        "/me/alerts?ticker=PETR4&target_price=40&direction=above",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    alert_id = create.json()["id"]

    # B tenta ver/apagar o alerta de A.
    check = await async_client.get(
        f"/me/alerts/{alert_id}/check",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert check.status_code == 404

    delete = await async_client.delete(
        f"/me/alerts/{alert_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert delete.status_code == 404
