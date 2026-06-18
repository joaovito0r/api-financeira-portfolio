"""
Repositório local com cache em SQLite.

Operações de leitura/escrita no banco local, com suporte a cache.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.cache import QUOTE_CACHE, CachePolicy
from app.repositories.local.models import (
    QuoteModel,
    get_session,
)


class LocalQuoteRepository:
    """Repositório local de cotações com cache.

    Armazena cotações em SQLite e verifica validade
    conforme a política de cache definida.
    """

    def __init__(self, cache_policy: CachePolicy = QUOTE_CACHE) -> None:
        self._cache_policy = cache_policy

    async def get(self, ticker: str) -> dict[str, Any] | None:
        """Busca cotação no cache local.

        Retorna None se não encontrado ou cache expirado.
        """
        async with get_session() as session:
            result = await session.execute(
                select(QuoteModel)
                .where(QuoteModel.ticker == ticker.upper())
                .order_by(QuoteModel.cached_at.desc())
            )
            quote = result.scalars().first()

            if not quote:
                return None

            if self._cache_policy.is_expired(quote.cached_at):
                return None

            return {
                "ticker": quote.ticker,
                "price": quote.price,
                "change": quote.change,
                "change_percent": quote.change_percent,
                "day_high": quote.day_high,
                "day_low": quote.day_low,
                "volume": quote.volume,
                "open": quote.open,
                "previous_close": quote.previous_close,
                "market_cap": quote.market_cap,
                "timestamp": quote.cached_at.isoformat(),
            }

    async def save(self, ticker: str, data: dict[str, Any]) -> dict[str, Any]:
        """Salva cotação no cache local."""
        async with get_session() as session:
            quote = QuoteModel(
                ticker=ticker.upper(),
                price=data.get("regularMarketPrice", 0),
                change=data.get("regularMarketChange", 0),
                change_percent=data.get("regularMarketChangePercent", 0),
                day_high=data.get("regularMarketDayHigh", 0),
                day_low=data.get("regularMarketDayLow", 0),
                volume=data.get("regularMarketVolume", 0),
                open=data.get("regularMarketOpen", 0),
                previous_close=data.get("regularMarketPreviousClose", 0),
                market_cap=data.get("marketCap"),
                cached_at=datetime.now(),
            )
            session.add(quote)
            await session.commit()

            return {
                "ticker": quote.ticker,
                "price": quote.price,
                "change": quote.change,
                "change_percent": quote.change_percent,
                "day_high": quote.day_high,
                "day_low": quote.day_low,
                "volume": quote.volume,
                "open": quote.open,
                "previous_close": quote.previous_close,
                "market_cap": quote.market_cap,
                "timestamp": quote.cached_at.isoformat(),
            }
