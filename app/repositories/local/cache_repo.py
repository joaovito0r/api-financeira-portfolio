"""Repositório de cache genérico (tabela cache_entries).

Armazena qualquer payload serializável em JSON, indexado por chave, com
expiração definida por uma CachePolicy passada na leitura/escrita.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.cache import CachePolicy
from app.repositories.local.models import CacheEntryModel, get_session


class GenericCacheRepository:
    """Cache chave→JSON em SQLite, com política de expiração por chamada."""

    async def get(self, key: str, policy: CachePolicy) -> Any | None:
        """Retorna o valor cacheado ou None se ausente/expirado."""
        async with get_session() as session:
            row = (
                await session.execute(
                    select(CacheEntryModel).where(CacheEntryModel.key == key)
                )
            ).scalars().first()
            if row is None or policy.is_expired(row.cached_at):
                return None
            return json.loads(row.payload)

    async def save(self, key: str, value: Any, policy: CachePolicy) -> Any:
        """Persiste (ou sobrescreve) o valor sob a chave e retorna o valor."""
        payload = json.dumps(value, default=str, ensure_ascii=False)
        async with get_session() as session:
            row = (
                await session.execute(
                    select(CacheEntryModel).where(CacheEntryModel.key == key)
                )
            ).scalars().first()
            if row is None:
                session.add(
                    CacheEntryModel(
                        key=key,
                        payload=payload,
                        policy=str(policy.ttl),
                        cached_at=datetime.now(),
                    )
                )
            else:
                row.payload = payload
                row.cached_at = datetime.now()
            await session.commit()
        return value
