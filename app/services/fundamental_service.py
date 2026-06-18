"""
Serviço de dados fundamentalistas.

Agrupa perfil, BP, DRE, indicadores e estatísticas.

NOTA: A brapi.dev retorna valores diretamente (sem wrapper .raw).
balanceSheetHistory e incomeStatementHistory são listas, não dicts.

Todas as consultas seguem o padrão cache-first: tenta ler do
GenericCacheRepository antes de chamar a brapi.dev; em caso de
cache-miss, busca na brapi e persiste o resultado no cache.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.cache import (
    BALANCE_SHEET_CACHE,
    INDICATOR_CACHE,
    PROFILE_CACHE,
    STATISTIC_CACHE,
)
from app.repositories.brapi.client import BrapiClient
from app.repositories.local.cache_repo import GenericCacheRepository


class FundamentalService:
    """Serviço de consulta de dados fundamentalistas."""

    def __init__(
        self, brapi_client: BrapiClient, cache_repo: GenericCacheRepository
    ) -> None:
        self._brapi = brapi_client
        self._cache = cache_repo

    @staticmethod
    def _parse_date(value: str | int | None) -> str | None:
        """Converte data para ISO, seja timestamp UNIX ou string ISO."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d")
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
        return None

    async def get_profile(self, ticker: str) -> dict[str, Any]:
        """Perfil da empresa (cache-first)."""
        key = f"profile:{ticker.upper()}"
        cached = await self._cache.get(key, PROFILE_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        raw = await self._brapi.quote(ticker, modules="summaryProfile")
        profile = raw.get("results", [{}])[0].get("summaryProfile", {})
        result = {
            "ticker": ticker.upper(),
            "address": profile.get("address1"),
            "city": profile.get("city"),
            "state": profile.get("state"),
            "country": profile.get("country"),
            "website": profile.get("website"),
            "industry": profile.get("industry"),
            "sector": profile.get("sector"),
            "description": profile.get("longBusinessSummary"),
            "employees": profile.get("fullTimeEmployees"),
        }
        return await self._cache.save(key, result, PROFILE_CACHE)  # type: ignore[no-any-return]

    async def get_balance_sheet(self, ticker: str) -> list[dict[str, Any]]:
        """Balanço Patrimonial (cache-first)."""
        key = f"balance:{ticker.upper()}"
        cached = await self._cache.get(key, BALANCE_SHEET_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        raw = await self._brapi.quote(ticker, modules="balanceSheetHistory")
        sheets = raw.get("results", [{}])[0].get("balanceSheetHistory", [])

        result = [
            {
                "ticker": ticker.upper(),
                "end_date": self._parse_date(bs.get("endDate")),
                "total_assets": bs.get("totalAssets"),
                "current_assets": bs.get("totalCurrentAssets"),
                "current_liabilities": bs.get("totalCurrentLiabilities"),
                "shareholder_equity": bs.get("totalShareholderEquity"),
                "long_term_debt": bs.get("longTermDebt"),
                "cash": bs.get("cash"),
            }
            for bs in sheets
        ]
        return await self._cache.save(key, result, BALANCE_SHEET_CACHE)  # type: ignore[no-any-return]

    async def get_income_statement(self, ticker: str) -> list[dict[str, Any]]:
        """DRE (cache-first)."""
        key = f"income:{ticker.upper()}"
        cached = await self._cache.get(key, BALANCE_SHEET_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        raw = await self._brapi.quote(ticker, modules="incomeStatementHistory")
        statements = raw.get("results", [{}])[0].get("incomeStatementHistory", [])

        result = [
            {
                "ticker": ticker.upper(),
                "end_date": self._parse_date(st.get("endDate")),
                "total_revenue": st.get("totalRevenue"),
                "cost_of_revenue": st.get("costOfRevenue"),
                "gross_profit": st.get("grossProfit"),
                "operating_income": st.get("operatingIncome"),
                "net_income": st.get("netIncome"),
                "ebitda": st.get("ebitda"),
            }
            for st in statements
        ]
        return await self._cache.save(key, result, BALANCE_SHEET_CACHE)  # type: ignore[no-any-return]

    async def get_indicators(self, ticker: str) -> dict[str, Any]:
        """Indicadores financeiros (cache-first)."""
        key = f"indicators:{ticker.upper()}"
        cached = await self._cache.get(key, INDICATOR_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        raw = await self._brapi.quote(ticker, modules="financialData")
        data = raw.get("results", [{}])[0].get("financialData", {})
        result = {
            "ticker": ticker.upper(),
            "current_price": data.get("currentPrice"),
            "target_price": data.get("targetMeanPrice"),
            "recommendation": data.get("recommendationKey"),
            "gross_margin": data.get("grossMargins"),
            "operating_margin": data.get("operatingMargins"),
            "profit_margin": data.get("profitMargins"),
            "roe": data.get("returnOnEquity"),
            "roa": data.get("returnOnAssets"),
            "revenue_growth": data.get("revenueGrowth"),
            "earnings_growth": data.get("earningsGrowth"),
            "debt_to_equity": data.get("debtToEquity"),
        }
        return await self._cache.save(key, result, INDICATOR_CACHE)  # type: ignore[no-any-return]

    async def get_statistics(self, ticker: str) -> dict[str, Any]:
        """Estatísticas-chave (cache-first)."""
        key = f"statistics:{ticker.upper()}"
        cached = await self._cache.get(key, STATISTIC_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        raw = await self._brapi.quote(ticker, modules="defaultKeyStatistics")
        data = raw.get("results", [{}])[0].get("defaultKeyStatistics", {})
        result = {
            "ticker": ticker.upper(),
            "price_to_book": data.get("priceToBook"),
            "forward_pe": data.get("forwardPE"),
            "trailing_pe": data.get("trailingPE"),
            "enterprise_value": data.get("enterpriseValue"),
            "ev_to_ebitda": data.get("enterpriseToEbitda"),
            "ev_to_revenue": data.get("enterpriseToRevenue"),
            "beta": data.get("beta"),
            "dividend_yield": data.get("dividendYield"),
            "book_value": data.get("bookValue"),
            "earnings_per_share": data.get("earningsPerShare"),
            "week_high_52": data.get("fiftyTwoWeekHigh"),
            "week_low_52": data.get("fiftyTwoWeekLow"),
        }
        return await self._cache.save(key, result, STATISTIC_CACHE)  # type: ignore[no-any-return]
