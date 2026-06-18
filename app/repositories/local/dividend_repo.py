"""
Repositório local de dividendos com cache perpétuo.

Uma vez salvos, dividendos passados nunca expiram.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.core.cache import DIVIDEND_CACHE
from app.repositories.local.models import DividendModel, get_session


class LocalDividendRepository:
    """Repositório local de dividendos com cache perpétuo."""

    def __init__(self) -> None:
        self._cache_policy = DIVIDEND_CACHE

    async def get(self, ticker: str) -> list[dict[str, Any]] | None:
        """Busca dividendos de um ativo no cache local."""
        async with get_session() as session:
            result = await session.execute(
                select(DividendModel)
                .where(DividendModel.ticker == ticker.upper())
                .order_by(DividendModel.date.desc())
            )
            dividends = result.scalars().all()

            if not dividends:
                return None

            return [
                {
                    "ticker": d.ticker,
                    "payment_date": d.date.isoformat(),
                    "value": d.value,
                    "type": d.type,
                    "reference_date": d.reference_date.isoformat()
                    if d.reference_date
                    else None,
                }
                for d in dividends
            ]

    async def save(
        self, ticker: str, dividends_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Salva dividendos no cache local.

        Os dados já devem vir no formato padronizado:
        [{payment_date, value, type, reference_date}, ...]
        """
        async with get_session() as session:
            saved = []
            for item in dividends_data:
                raw_date = item.get("payment_date", "")
                if isinstance(raw_date, str) and raw_date:
                    parsed_date = date.fromisoformat(raw_date[:10])
                else:
                    continue  # pula itens sem data válida

                ref_date = item.get("reference_date")
                if ref_date and isinstance(ref_date, str):
                    ref_date = date.fromisoformat(ref_date[:10])

                model = DividendModel(
                    ticker=ticker.upper(),
                    date=parsed_date,
                    value=item.get("value", 0),
                    type=item.get("type", ""),
                    reference_date=ref_date,
                )
                session.add(model)
                saved.append(
                    {
                        "ticker": model.ticker,
                        "payment_date": model.date.isoformat(),
                        "value": model.value,
                        "type": model.type,
                        "reference_date": model.reference_date.isoformat()
                        if model.reference_date
                        else None,
                    }
                )
            await session.commit()
            return saved
