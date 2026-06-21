"""
Repositório local de preços históricos OHLCV.

Cache perpétuo: dados históricos são imutáveis após o pregão.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.core.cache import OHLCV_CACHE
from app.repositories.local.models import OHLCVModel, get_session


class LocalOHLCVRepository:
    """Repositório local de OHLCV com cache perpétuo."""

    def __init__(self) -> None:
        self._cache_policy = OHLCV_CACHE

    async def get(
        self, ticker: str, range: str, interval: str
    ) -> list[dict[str, Any]] | None:
        """Busca histórico OHLCV de um ativo no cache local.

        O cache é por ticker+range+interval: combinações diferentes desses
        filtros descrevem séries de dados diferentes (ex.: 5d/1d não é um
        subconjunto óbvio de 5y/1mo), então cada combinação tem sua própria
        entrada — não basta existir cache para o ticker.
        """
        async with get_session() as session:
            result = await session.execute(
                select(OHLCVModel)
                .where(OHLCVModel.ticker == ticker.upper())
                .where(OHLCVModel.range == range)
                .where(OHLCVModel.interval == interval)
                .order_by(OHLCVModel.date)
            )
            records = result.scalars().all()

            if not records:
                return None

            return [
                {
                    "ticker": r.ticker,
                    "trade_date": r.date.isoformat(),
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in records
            ]

    async def save(
        self, ticker: str, range: str, interval: str, history: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Salva histórico OHLCV no cache local, sob a chave ticker+range+interval."""
        async with get_session() as session:
            saved = []
            for item in history:
                raw_date = item.get("date", "")
                if isinstance(raw_date, (int, float)):
                    from datetime import datetime

                    item_date = datetime.fromtimestamp(raw_date).date()
                else:
                    item_date = date.fromisoformat(str(raw_date)[:10])

                model = OHLCVModel(
                    ticker=ticker.upper(),
                    range=range,
                    interval=interval,
                    date=item_date,
                    open=item.get("open", 0),
                    high=item.get("high", 0),
                    low=item.get("low", 0),
                    close=item.get("close", 0),
                    volume=item.get("volume", 0),
                )
                session.add(model)
                saved.append(
                    {
                        "ticker": model.ticker,
                        "trade_date": model.date.isoformat(),
                        "open": model.open,
                        "high": model.high,
                        "low": model.low,
                        "close": model.close,
                        "volume": model.volume,
                    }
                )
            await session.commit()
            return saved
