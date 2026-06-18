"""
Testes de segurança: validação de ticker e isolamento multi-tenant.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.validation import normalize_ticker

# ── Validação de ticker (unidade) ──────────────────────────────


@pytest.mark.parametrize(
    ("raw", "esperado"), [("petr4", "PETR4"), (" vale3 ", "VALE3")]
)
def test_normalize_ticker_valido(raw: str, esperado: str) -> None:
    assert normalize_ticker(raw) == esperado


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "PETR4?foo=bar",
        "../../etc/passwd",
        "'; DROP TABLE users;--",
        "PE TR4",
        "A" * 11,
    ],
)
def test_normalize_ticker_invalido(raw: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        normalize_ticker(raw)


# ── Helpers ────────────────────────────────────────────────────


async def _registrar(client: AsyncClient) -> str:
    email = f"sec_{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"name": "User", "email": email, "password": "senha_segura_123"},
    )
    assert r.status_code == 200
    return str(r.json()["access_token"])


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Validação de ticker (integração) ───────────────────────────


@pytest.mark.asyncio
async def test_add_item_ticker_invalido_retorna_422(async_client: AsyncClient) -> None:
    token = await _registrar(async_client)
    wid = (
        await async_client.post(
            "/me/watchlists", headers=_h(token), params={"name": "x"}
        )
    ).json()["id"]
    r = await async_client.post(
        f"/me/watchlists/{wid}/items",
        headers=_h(token),
        params={"ticker": "'; DROP TABLE users;--"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_criar_alerta_ticker_invalido_retorna_422(
    async_client: AsyncClient,
) -> None:
    token = await _registrar(async_client)
    r = await async_client.post(
        "/me/alerts",
        headers=_h(token),
        params={"ticker": "PETR4?x=1", "target_price": 10, "direction": "below"},
    )
    assert r.status_code == 422


# ── Multi-tenancy ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_usuario_nao_acessa_watchlist_de_outro(async_client: AsyncClient) -> None:
    token_a = await _registrar(async_client)
    token_b = await _registrar(async_client)
    wid = (
        await async_client.post(
            "/me/watchlists", headers=_h(token_a), params={"name": "Carteira A"}
        )
    ).json()["id"]

    # B não vê a watchlist de A na listagem
    lista_b = await async_client.get("/me/watchlists", headers=_h(token_b))
    assert lista_b.json()["total"] == 0

    # B não consegue ler/alterar/apagar a watchlist de A por ID
    assert (
        await async_client.get(f"/me/watchlists/{wid}/items", headers=_h(token_b))
    ).status_code == 404
    assert (
        await async_client.patch(
            f"/me/watchlists/{wid}", headers=_h(token_b), params={"name": "hack"}
        )
    ).status_code == 404
    assert (
        await async_client.delete(f"/me/watchlists/{wid}", headers=_h(token_b))
    ).status_code == 404


@pytest.mark.asyncio
async def test_usuario_nao_acessa_alerta_de_outro(async_client: AsyncClient) -> None:
    token_a = await _registrar(async_client)
    token_b = await _registrar(async_client)
    aid = (
        await async_client.post(
            "/me/alerts",
            headers=_h(token_a),
            params={"ticker": "PETR4", "target_price": 10, "direction": "below"},
        )
    ).json()["id"]

    assert (await async_client.get("/me/alerts", headers=_h(token_b))).json()[
        "total"
    ] == 0
    assert (
        await async_client.get(f"/me/alerts/{aid}/check", headers=_h(token_b))
    ).status_code == 404
    assert (
        await async_client.delete(f"/me/alerts/{aid}", headers=_h(token_b))
    ).status_code == 404


@pytest.mark.asyncio
async def test_rota_protegida_sem_token_retorna_401(async_client: AsyncClient) -> None:
    assert (await async_client.get("/me/watchlists")).status_code == 401
    assert (await async_client.get("/auth/me")).status_code == 401


# ── Não vazamento de dados sensíveis no corpo da resposta ──────


@pytest.mark.asyncio
async def test_respostas_nao_vazam_hash_de_senha(async_client: AsyncClient) -> None:
    """Nenhuma resposta de auth deve conter hash de senha ou campo password."""
    email = f"leak_{uuid.uuid4().hex[:10]}@example.com"
    reg = await async_client.post(
        "/auth/register",
        json={"name": "Leak", "email": email, "password": "senha_segura_123"},
    )
    token = reg.json()["access_token"]
    login = await async_client.post(
        "/auth/login", json={"email": email, "password": "senha_segura_123"}
    )
    me = await async_client.get("/auth/me", headers=_h(token))

    for resp in (reg, login, me):
        corpo = resp.text.lower()
        assert "password_hash" not in corpo
        assert "$argon" not in corpo
        assert "hash" not in corpo


@pytest.mark.asyncio
async def test_erro_validacao_nao_ecoa_valor_da_senha(
    async_client: AsyncClient,
) -> None:
    """O erro 422 de senha curta não pode conter o valor enviado."""
    senha = "sEcReT7"  # 7 chars → inválida (mínimo 8)
    r = await async_client.post(
        "/auth/register",
        json={"name": "Teste", "email": "x422@example.com", "password": senha},
    )
    assert r.status_code == 422
    assert senha not in r.text  # só o nome do campo, nunca o valor


@pytest.mark.asyncio
async def test_token_so_aparece_em_login_e_registro(
    async_client: AsyncClient,
) -> None:
    """access_token não deve aparecer em respostas que não sejam auth."""
    token = await _registrar(async_client)
    me = await async_client.get("/auth/me", headers=_h(token))
    wl = await async_client.get("/me/watchlists", headers=_h(token))
    assert "access_token" not in me.text
    assert "access_token" not in wl.text
