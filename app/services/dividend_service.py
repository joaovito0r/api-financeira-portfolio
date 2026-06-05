"""
Serviço de dividendos.

Cache-first: busca dividendos no SQLite antes de consultar a brapi.dev.
A brapi.dev retorna dividendos em formato {cashDividends: [...], stockDividends: [...]}.
"""

from __future__ import annotations

from app.repositories.brapi.client import BrapiClient
from app.repositories.local.dividend_repo import LocalDividendRepository


class DividendService:
    """Serviço de consulta de dividendos."""

    def __init__(
        self,
        brapi_client: BrapiClient,
        local_repo: LocalDividendRepository,
    ) -> None:
        self._brapi = brapi_client
        self._local = local_repo

    async def get_dividends(self, ticker: str) -> list[dict]:
        """Busca dividendos de um ativo com cache."""
        cached = await self._local.get(ticker)
        if cached:
            return cached

        raw = await self._brapi.dividends(ticker)
        div_data = raw.get("results", [{}])[0].get("dividendsData", {})

        # brapi.dev retorna {cashDividends: [...], stockDividends: [...], \n        # subscriptions: [...]}
        cash_dividends = div_data.get("cashDividends", [])
        if not cash_dividends:
            return []

        # Converte pro formato padrão
        converted = []
        for item in cash_dividends:
            converted.append(
                {
                    "payment_date": item.get("paymentDate", "")[:10],
                    "value": item.get("rate", 0),
                    "type": self._map_label(item.get("label", "")),
                    "reference_date": (
                        item.get("lastDatePrior", "")[:10]
                        if item.get("lastDatePrior")
                        else None
                    ),
                }
            )

        return await self._local.save(ticker, converted)

    def _map_label(self, label: str) -> str:
        """Mapeia label da brapi.dev para tipo padronizado."""
        mapping = {
            "RENDIMENTO": "DIVIDENDO",
            "JCP": "JCP",
            "BONIFICACAO": "BONIFICACAO",
            "JUROS": "JCP",
        }
        return mapping.get(label.upper(), label)
