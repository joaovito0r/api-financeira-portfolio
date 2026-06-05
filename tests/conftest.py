"""
Fixtures compartilhadas para os testes.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.repositories.local.models import init_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_app() -> AsyncGenerator[None, None]:
    """Inicializa banco e cliente brapi (como o lifespan faz)."""
    init_db()
    # Tenta inicializar o cliente brapi; se não tiver token, segue sem
    try:
        from app.repositories.brapi.client import BrapiClient

        app.state.brapi_client = BrapiClient()
    except ValueError:
        # Token não configurado nos testes — usa mock
        from unittest.mock import AsyncMock

        mock = AsyncMock()
        mock.quote = AsyncMock(return_value={"results": [{}]})
        mock.close = AsyncMock()
        app.state.brapi_client = mock
    yield
    await app.state.brapi_client.close()


@pytest.fixture
def app_instance():
    """Retorna a instância da aplicação FastAPI."""
    return app


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP assíncrono para testar a API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
