"""Cache quente: reaquece, em background, o universo observado.

Universo observado = tickers distintos presentes em watchlists e alertas.
Roda só durante o pregão e respeita um teto de tickers por ciclo para não
estourar a quota do plano free (regra N/T ≤ ~1,7).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import select

from app.config import settings
from app.core.concurrency import gather_limited
from app.core.market_hours import SAO_PAULO, is_market_open
from app.repositories.local.models import (
    AlertModel,
    WatchlistItemModel,
    get_session,
)
from app.repositories.local.quote_repo import LocalQuoteRepository
from app.services.quote_service import QuoteService

logger = logging.getLogger("warm_cache")


async def watched_universe() -> list[str]:
    """Tickers distintos em watchlists ∪ alertas, em maiúsculas."""
    async with get_session() as session:
        wl = await session.execute(select(WatchlistItemModel.ticker).distinct())
        al = await session.execute(select(AlertModel.ticker).distinct())
    tickers = {t.upper() for (t,) in wl.all()} | {t.upper() for (t,) in al.all()}
    return sorted(tickers)


async def refresh_universe(app: FastAPI) -> int:
    """Reaquece o cache de cotação do universo (até o teto). Retorna nº processado."""
    tickers = (await watched_universe())[: settings.warm_cache_max_tickers]
    if not tickers:
        return 0
    service = QuoteService(
        brapi_client=app.state.brapi_client, local_repo=LocalQuoteRepository()
    )
    # get_quote é cache-first: só chama a brapi para os tickers com cache expirado.
    await gather_limited(*(service.get_quote(t) for t in tickers))
    return len(tickers)


async def warm_cache_loop(app: FastAPI) -> None:
    """Loop de background: reaquece o universo no pregão, ocioso fora dele."""
    while True:
        try:
            if is_market_open(datetime.now(SAO_PAULO)):
                n = await refresh_universe(app)
                logger.info("warm cache: %d tickers reaquecidos", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — loop não pode morrer por erro pontual
            logger.exception("warm cache: falha no ciclo")
        await asyncio.sleep(settings.warm_cache_interval_sec)
