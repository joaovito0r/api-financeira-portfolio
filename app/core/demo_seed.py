"""Conta demo para recrutadores/visitantes explorarem a API sem cadastro.

Mesmo padrão de `app/core/warm_cache.py` e `app/core/account_purge.py`: task
asyncio de longa duração, iniciada/encerrada no `lifespan` do FastAPI.

A conta (`settings.demo_account_email`) é criada uma vez no startup e depois
tem sua carteira, listas e alertas restaurados ao retrato fixo em
`app/core/demo_data.py` a cada `settings.demo_reset_interval_sec` — assim
qualquer exploração de um visitante é desfeita automaticamente para o
próximo. Email e senha da conta nunca são alterados pelo reset porque o
guard fica em `AuthService` (`change_password`/`request_deletion` recusam a
operação para `is_demo=True`), não aqui.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import delete, select

from app.config import settings
from app.core.demo_data import DEMO_ALERTS, DEMO_NAME, DEMO_PORTFOLIO, DEMO_WATCHLISTS
from app.core.security import hash_password
from app.core.time_utils import utcnow_naive
from app.repositories.local.models import (
    AlertModel,
    PortfolioPositionModel,
    UserModel,
    WatchlistItemModel,
    WatchlistModel,
    get_session,
)

logger = logging.getLogger("demo_seed")


async def ensure_demo_user() -> None:
    """Cria a conta demo se ainda não existir; idempotente.

    Não recria se já existir (mesmo que os dados relacionados tenham sido
    apagados por algum motivo) — `reset_demo_data` cuida de repopular.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == settings.demo_account_email)
        )
        user = result.scalars().first()
        if user is None:
            user = UserModel(
                name=DEMO_NAME,
                email=settings.demo_account_email,
                password_hash=hash_password(settings.demo_account_password),
                is_demo=True,
            )
            session.add(user)
            await session.commit()
            logger.info("conta demo criada: %s", settings.demo_account_email)
        elif not user.is_demo:
            # Defesa em profundidade: se por algum motivo o e-mail configurado
            # já existir sem a flag (ex.: mudança de config), não sequestra
            # uma conta de usuário real marcando-a como demo.
            logger.warning(
                "e-mail configurado para demo (%s) já existe e não é demo; "
                "pulando ensure_demo_user",
                settings.demo_account_email,
            )


async def reset_demo_data() -> bool:
    """Restaura nome, carteira, listas e alertas da conta demo ao retrato fixo.

    Returns:
        True se a conta demo foi encontrada e resetada; False se não existir
        ainda (ex.: `demo_account_enabled` acabou de ser ligado).
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(
                UserModel.email == settings.demo_account_email,
                UserModel.is_demo.is_(True),
            )
        )
        user = result.scalars().first()
        if user is None:
            return False

        user.name = DEMO_NAME
        user.deleted_at = None

        await session.execute(
            delete(WatchlistItemModel).where(
                WatchlistItemModel.watchlist_id.in_(
                    select(WatchlistModel.id).where(WatchlistModel.user_id == user.id)
                )
            )
        )
        await session.execute(
            delete(WatchlistModel).where(WatchlistModel.user_id == user.id)
        )
        await session.execute(delete(AlertModel).where(AlertModel.user_id == user.id))
        await session.execute(
            delete(PortfolioPositionModel).where(
                PortfolioPositionModel.user_id == user.id
            )
        )

        for position in DEMO_PORTFOLIO:
            session.add(PortfolioPositionModel(user_id=user.id, **position))

        for watchlist in DEMO_WATCHLISTS:
            wl = WatchlistModel(user_id=user.id, name=watchlist["name"])
            session.add(wl)
            await session.flush()  # garante wl.id antes de referenciar nos itens
            for item in watchlist["items"]:
                session.add(WatchlistItemModel(watchlist_id=wl.id, **item))

        now = utcnow_naive()
        for alert in DEMO_ALERTS:
            session.add(
                AlertModel(
                    user_id=user.id,
                    ticker=alert["ticker"],
                    target_price=alert["target_price"],
                    direction=alert["direction"],
                    triggered=alert["triggered"],
                    triggered_at=now if alert["triggered"] else None,
                )
            )

        await session.commit()
        return True


async def demo_reset_loop() -> None:
    """Loop de background: restaura a conta demo periodicamente."""
    await ensure_demo_user()
    await reset_demo_data()
    while True:
        try:
            await asyncio.sleep(settings.demo_reset_interval_sec)
            await reset_demo_data()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — loop não pode morrer por erro pontual
            logger.exception("reset da conta demo: falha no ciclo")
