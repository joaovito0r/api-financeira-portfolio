"""Testes do cache genérico (cache_entries)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.cache import CachePolicy
from app.repositories.local.cache_repo import GenericCacheRepository
from app.repositories.local.models import init_db


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
