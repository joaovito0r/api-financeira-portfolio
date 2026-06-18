"""Testes do cache genérico (cache_entries)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.cache import CachePolicy
from app.repositories.local.cache_repo import GenericCacheRepository
from app.repositories.local.models import init_db
from app.services.fundamental_service import FundamentalService


@pytest.mark.asyncio
async def test_save_e_get_roundtrip() -> None:
    await init_db()
    repo = GenericCacheRepository()
    policy = CachePolicy(ttl=3600)
    await repo.save("profile:PETR4", {"sector": "Energia"}, policy)
    got = await repo.get("profile:PETR4", policy)
    assert got == {"sector": "Energia"}


@pytest.mark.asyncio
async def test_get_retorna_none_quando_expirado() -> None:
    await init_db()
    repo = GenericCacheRepository()
    expired = CachePolicy(ttl=1)
    await repo.save("k:expira", {"v": 1}, expired)
    # Força expiração reescrevendo cached_at no passado
    from sqlalchemy import select

    from app.repositories.local.models import CacheEntryModel, get_session

    async with get_session() as session:
        row = (
            await session.execute(
                select(CacheEntryModel).where(CacheEntryModel.key == "k:expira")
            )
        ).scalars().first()
        assert row is not None
        row.cached_at = datetime.now() - timedelta(seconds=10)
        await session.commit()
    assert await repo.get("k:expira", expired) is None


@pytest.mark.asyncio
async def test_save_sobrescreve_mesma_chave() -> None:
    await init_db()
    repo = GenericCacheRepository()
    policy = CachePolicy(ttl=3600)
    await repo.save("k:dup", {"v": 1}, policy)
    await repo.save("k:dup", {"v": 2}, policy)
    assert await repo.get("k:dup", policy) == {"v": 2}


@pytest.mark.asyncio
async def test_fundamental_usa_cache_no_segundo_acesso() -> None:
    await init_db()
    brapi = AsyncMock()
    brapi.quote = AsyncMock(
        return_value={"results": [{"summaryProfile": {"sector": "Energia"}}]}
    )
    repo = GenericCacheRepository()
    # Limpa chave para teste determinístico
    from sqlalchemy import delete

    from app.repositories.local.models import CacheEntryModel, get_session

    async with get_session() as session:
        await session.execute(
            delete(CacheEntryModel).where(CacheEntryModel.key == "profile:PETR4")
        )
        await session.commit()

    service = FundamentalService(brapi_client=brapi, cache_repo=repo)
    first = await service.get_profile("PETR4")
    second = await service.get_profile("PETR4")

    assert first["sector"] == "Energia"
    assert second["sector"] == "Energia"
    brapi.quote.assert_awaited_once()  # 2º acesso veio do cache


@pytest.mark.asyncio
async def test_lista_ativos_usa_cache() -> None:
    """Testa que lista de ativos é cache-first (2º acesso não bate brapi)."""
    await init_db()
    brapi = AsyncMock()
    brapi.list_assets = AsyncMock(
        return_value={"stocks": [{"stock": "PETR4", "name": "Petrobras"}]}
    )
    from sqlalchemy import delete

    from app.repositories.local.models import CacheEntryModel, get_session

    async with get_session() as session:
        await session.execute(
            delete(CacheEntryModel).where(CacheEntryModel.key == "assets:all::")
        )
        await session.commit()

    from app.core.cache import ASSET_LIST_CACHE  # noqa: F401
    from app.services.asset_service import AssetService

    service = AssetService(brapi_client=brapi, cache_repo=GenericCacheRepository())
    await service.list_assets()
    await service.list_assets()
    brapi.list_assets.assert_awaited_once()
