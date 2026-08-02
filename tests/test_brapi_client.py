"""
Testes unitários do BrapiClient: parsing de sucesso e tratamento de erros
de rede/HTTP (timeout, status de erro, falha de conexão), sem bater na
API real — usa httpx.MockTransport.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from app.repositories.brapi.client import BrapiClient


def make_client(handler) -> BrapiClient:
    """Cria um BrapiClient real, mas troca o transporte HTTP por um mock."""
    client = BrapiClient()
    client._client = httpx.AsyncClient(
        base_url=BrapiClient.BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    return client


@pytest.mark.asyncio
async def test_quote_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/quote/PETR4"
        return httpx.Response(200, json={"results": [{"regularMarketPrice": 38.0}]})

    client = make_client(handler)
    data = await client.quote("PETR4")
    assert data["results"][0]["regularMarketPrice"] == 38.0
    await client.close()


@pytest.mark.asyncio
async def test_quote_with_modules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["modules"] == "financialData"
        return httpx.Response(200, json={"results": [{}]})

    client = make_client(handler)
    await client.quote("PETR4", modules="financialData")
    await client.close()


@pytest.mark.asyncio
async def test_quote_invalid_ticker_raises_422() -> None:
    client = make_client(lambda _request: httpx.Response(200, json={}))
    with pytest.raises(HTTPException) as exc_info:
        await client.quote("***")
    assert exc_info.value.status_code == 422
    await client.close()


@pytest.mark.asyncio
async def test_multiple_quote() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["tickers"] == "PETR4,VALE3"
        return httpx.Response(200, json={"results": [{}, {}]})

    client = make_client(handler)
    data = await client.multiple_quote(["petr4", "vale3"])
    assert len(data["results"]) == 2
    await client.close()


@pytest.mark.asyncio
async def test_historical() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["range"] == "5y"
        assert request.url.params["interval"] == "1mo"
        return httpx.Response(200, json={"results": [{"historicalDataPrice": []}]})

    client = make_client(handler)
    await client.historical("VALE3", range="5y", interval="1mo")
    await client.close()


@pytest.mark.asyncio
async def test_dividends() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["dividends"] == "true"
        return httpx.Response(200, json={"results": [{}]})

    client = make_client(handler)
    await client.dividends("ITUB4")
    await client.close()


@pytest.mark.asyncio
async def test_list_assets_with_filters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "petro"
        assert request.url.params["sector"] == "Energy"
        return httpx.Response(200, json={"stocks": []})

    client = make_client(handler)
    await client.list_assets(search="petro", sector="Energy")
    await client.close()


@pytest.mark.asyncio
async def test_available() -> None:
    client = make_client(lambda _request: httpx.Response(200, json={"stocks": []}))
    data = await client.available()
    assert data == {"stocks": []}
    await client.close()


@pytest.mark.asyncio
async def test_health() -> None:
    client = make_client(lambda _request: httpx.Response(200, json={"status": "ok"}))
    data = await client.health()
    assert data == {"status": "ok"}
    await client.close()


@pytest.mark.asyncio
async def test_dictionary_with_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "pl"
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.dictionary(search="pl")
    await client.close()


@pytest.mark.asyncio
async def test_get_timeout_raises_504() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = make_client(handler)
    with pytest.raises(HTTPException) as exc_info:
        await client.health()
    assert exc_info.value.status_code == 504
    await client.close()


@pytest.mark.asyncio
async def test_get_http_status_error_propagates_status() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = make_client(handler)
    with pytest.raises(HTTPException) as exc_info:
        await client.quote("PETR4")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail
    await client.close()

    async def raising_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client2 = make_client(raising_handler)
    with pytest.raises(HTTPException) as exc_info:
        await client2.health()
    assert exc_info.value.status_code == 503
    await client2.close()


def test_init_without_token_raises() -> None:
    from app.config import settings

    original = settings.brapi_token
    settings.brapi_token = ""
    try:
        with pytest.raises(ValueError, match="BRAPI_TOKEN"):
            BrapiClient()
    finally:
        settings.brapi_token = original
