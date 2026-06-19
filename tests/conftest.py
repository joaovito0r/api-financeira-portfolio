"""
Fixtures compartilhadas para os testes.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import AsyncGenerator

# Isola o banco de testes do banco de dev (data/financeira.db): precisa ser
# definido antes de qualquer import de app.*, porque o engine é criado no
# nível de módulo em app/repositories/local/models.py, no momento do import.
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(
    suffix=".db", prefix="financeira_test_"
)
os.close(_TEST_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories.local.models import engine, init_db  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_app() -> AsyncGenerator[None, None]:
    """Inicializa banco isolado e sobrescreve cliente brapi com mock para testes."""
    await init_db()
    # Desliga rate limiting por padrão: evita que a suíte (várias chamadas
    # seguidas às rotas de watchlist/alert) estoure os baldes globais.
    # Os testes específicos de rate limit religam via monkeypatch.
    settings.rate_limit_enabled = False
    # Desliga o cache quente: o lifespan não roda no ASGITransport por padrão,
    # mas deixamos explícito para evitar surpresa se algum teste usar
    # LifespanManager — a task de background não deve competir com a suíte.
    settings.warm_cache_enabled = False
    from unittest.mock import AsyncMock

    mock = AsyncMock()
    mock.quote = AsyncMock(return_value={"results": [{}]})
    mock.multiple_quote = AsyncMock(return_value={"results": [{}, {}]})
    mock.available = AsyncMock(return_value={"stocks": []})
    mock.historical = AsyncMock(return_value={"historical_data": []})
    mock.list_assets = AsyncMock(return_value={"stocks": []})
    mock.dividends = AsyncMock(return_value={"dividends": {"cashDividends": []}})
    mock.health = AsyncMock(return_value={"status": "ok"})
    mock.close = AsyncMock()
    mock.dictionary = AsyncMock(return_value={})
    app.state.brapi_client = mock
    yield
    await app.state.brapi_client.close()
    await engine.dispose()
    for suffix in ("", "-wal", "-shm", "-journal"):
        with contextlib.suppress(FileNotFoundError):
            os.remove(_TEST_DB_PATH + suffix)


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
