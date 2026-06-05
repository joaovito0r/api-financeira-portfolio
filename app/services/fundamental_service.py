"""
Serviço de dados fundamentalistas.

Agrupa perfil, BP, DRE, indicadores e estatísticas.

NOTA: A brapi.dev retorna valores diretamente (sem wrapper .raw).
balanceSheetHistory e incomeStatementHistory são listas, não dicts.
"""

from __future__ import annotations

from datetime import datetime

from app.repositories.brapi.client import BrapiClient


class FundamentalService:
    """Serviço de consulta de dados fundamentalistas."""

    def __init__(self, brapi_client: BrapiClient) -> None:
        self._brapi = brapi_client

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

    async def get_profile(self, ticker: str) -> dict:
        """Perfil da empresa."""
        raw = await self._brapi.quote(ticker, modules="summaryProfile")
        profile = raw.get("results", [{}])[0].get("summaryProfile", {})
        return {
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

    async def get_balance_sheet(self, ticker: str) -> list[dict]:
        """Balanço Patrimonial."""
        raw = await self._brapi.quote(ticker, modules="balanceSheetHistory")
        sheets = raw.get("results", [{}])[0].get("balanceSheetHistory", [])

        return [
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

    async def get_income_statement(self, ticker: str) -> list[dict]:
        """DRE."""
        raw = await self._brapi.quote(ticker, modules="incomeStatementHistory")
        statements = raw.get("results", [{}])[0].get("incomeStatementHistory", [])

        return [
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

    async def get_indicators(self, ticker: str) -> dict:
        """Indicadores financeiros."""
        raw = await self._brapi.quote(ticker, modules="financialData")
        data = raw.get("results", [{}])[0].get("financialData", {})
        return {
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

    async def get_statistics(self, ticker: str) -> dict:
        """Estatísticas-chave."""
        raw = await self._brapi.quote(ticker, modules="defaultKeyStatistics")
        data = raw.get("results", [{}])[0].get("defaultKeyStatistics", {})
        return {
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
