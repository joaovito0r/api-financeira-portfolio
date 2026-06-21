"""Purge definitivo de contas marcadas para exclusão (soft delete) cuja janela
de recuperação expirou.

Mesmo padrão de `app/core/warm_cache.py`: task asyncio de longa duração,
iniciada/encerrada no `lifespan` do FastAPI, sem dependência de cron externo.
"""

from __future__ import annotations

import asyncio
import datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.time_utils import utcnow_naive
from app.repositories.local.models import UserModel, WatchlistModel, get_session

logger = logging.getLogger("account_purge")

_CHECK_INTERVAL_SEC = 3600  # 1h — não é sensível a quota de API externa


async def purge_expired_accounts() -> int:
    """Apaga permanentemente contas cuja janela de recuperação expirou.

    Returns:
        Quantidade de contas removidas neste ciclo.
    """
    cutoff = utcnow_naive() - datetime.timedelta(
        days=settings.account_deletion_grace_days
    )
    async with get_session() as session:
        result = await session.execute(
            select(UserModel)
            .where(UserModel.deleted_at.is_not(None))
            .where(UserModel.deleted_at <= cutoff)
            .options(
                selectinload(UserModel.watchlists).selectinload(
                    WatchlistModel.items
                ),
                selectinload(UserModel.alerts),
                selectinload(UserModel.portfolio_positions),
            )
        )
        expired_users = result.scalars().all()
        for user in expired_users:
            await session.delete(user)
        await session.commit()
        return len(expired_users)


async def purge_expired_accounts_loop() -> None:
    """Loop de background: verifica contas expiradas a cada hora."""
    while True:
        try:
            n = await purge_expired_accounts()
            if n:
                logger.info("purge de contas: %d conta(s) removida(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — loop não pode morrer por erro pontual
            logger.exception("purge de contas: falha no ciclo")
        await asyncio.sleep(_CHECK_INTERVAL_SEC)
