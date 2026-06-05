"""
Serviço de relatório de ativos.

Gera um relatório completo de um ativo com todas as métricas
disponíveis: perfil, valuation, performance, dividendos, saúde financeira.
"""

from __future__ import annotations

from app.repositories.brapi.client import BrapiClient


class ReportService:
    """Serviço de geração de relatório de ativos."""

    def __init__(self, brapi_client: BrapiClient) -> None:
        self._brapi = brapi_client

    async def generate_report(self, ticker: str) -> dict:
        """Gera relatório completo de um ativo."""
        ticker = ticker.upper()

        # 1. Cotação + dados básicos
        quote_raw = await self._brapi.quote(ticker)
        quote = quote_raw.get("results", [{}])[0]

        # 2. Perfil
        prof_raw = await self._brapi.quote(ticker, modules="summaryProfile")
        profile = prof_raw.get("results", [{}])[0].get("summaryProfile", {})

        # 3. Indicadores
        fin_raw = await self._brapi.quote(ticker, modules="financialData")
        fin = fin_raw.get("results", [{}])[0].get("financialData", {})

        # 4. Estatísticas
        stats_raw = await self._brapi.quote(ticker, modules="defaultKeyStatistics")
        stats = stats_raw.get("results", [{}])[0].get("defaultKeyStatistics", {})

        # 5. Histórico recente (1 ano para calcular retornos)
        hist_raw = await self._brapi.historical(ticker, range="1y", interval="1d")
        hist_data = hist_raw.get("results", [{}])[0].get("historicalDataPrice", [])

        # Calcula retornos
        returns = self._calculate_returns(hist_data)

        # 6. Dividendos
        div_raw = await self._brapi.dividends(ticker)
        div_data = div_raw.get("results", [{}])[0].get("dividendsData", {})
        cash_divs = div_data.get("cashDividends", [])

        # 7. BP (último)
        bs_raw = await self._brapi.quote(ticker, modules="balanceSheetHistory")
        bs_list = bs_raw.get("results", [{}])[0].get("balanceSheetHistory", [])
        latest_bs = bs_list[0] if bs_list else {}

        # 8. DRE (último)
        dre_raw = await self._brapi.quote(ticker, modules="incomeStatementHistory")
        dre_list = dre_raw.get("results", [{}])[0].get("incomeStatementHistory", [])
        latest_dre = dre_list[0] if dre_list else {}

        from datetime import datetime, timedelta, timezone

        hoje = datetime.now(timezone.utc)
        um_ano_atras = hoje - timedelta(days=365)

        def parse_date(ds: str) -> datetime:
            """Converte data ISO pra datetime com timezone."""
            clean = ds[:10].replace("Z", "")
            return datetime.fromisoformat(clean).replace(tzinfo=timezone.utc)

        divs_recentes = [
            d
            for d in cash_divs
            if d.get("paymentDate") and parse_date(d["paymentDate"]) > um_ano_atras
        ]

        total_divs_12m = sum(d.get("rate", 0) for d in divs_recentes)

        # Últimos 6 dividendos (mais recentes primeiro)
        divs_ordenados = sorted(
            cash_divs,
            key=lambda d: d.get("paymentDate", ""),
            reverse=True,
        )
        proximo_pagamento = (
            divs_ordenados[0].get("paymentDate", "")[:10]
            if divs_ordenados
            else None
        )

        return {
            "ticker": ticker,
            "gerado_em": __import__("datetime").datetime.now().isoformat(),
            "visao_geral": {
                "empresa": profile.get("longName", quote.get("shortName", "")),
                "setor": profile.get("sector"),
                "industria": profile.get("industry"),
                "descricao": profile.get("longBusinessSummary"),
                "site": profile.get("website"),
                "funcionarios": profile.get("fullTimeEmployees"),
                "preco": quote.get("regularMarketPrice"),
                "variacao_percentual": quote.get("regularMarketChangePercent"),
                "recomendacao": fin.get("recommendationKey"),
                "preco_alvo": fin.get("targetMeanPrice"),
                "num_analistas": fin.get("numberOfAnalystOpinions"),
            },
            "performance": {
                "retorno_1_mes": returns.get("1m"),
                "retorno_6_meses": returns.get("6m"),
                "retorno_1_ano": returns.get("1y"),
                "maxima_52_sem": quote.get("fiftyTwoWeekHigh"),
                "minima_52_sem": quote.get("fiftyTwoWeekLow"),
                "beta": stats.get("beta"),
            },
            "valuation": {
                "pl_corrente": stats.get("trailingPE"),
                "pl_futuro": stats.get("forwardPE"),
                "pvp": stats.get("priceToBook"),
                "ev_ebitda": stats.get("enterpriseToEbitda"),
                "ev_receita": stats.get("enterpriseToRevenue"),
                "enterprise_value": stats.get("enterpriseValue"),
                "vpa": stats.get("bookValue"),
                "lpa": stats.get("earningsPerShare"),
            },
            "indicadores": {
                "margem_bruta": fin.get("grossMargins"),
                "margem_operacional": fin.get("operatingMargins"),
                "margem_liquida": fin.get("profitMargins"),
                "roe": fin.get("returnOnEquity"),
                "roa": fin.get("returnOnAssets"),
                "divida_pl": fin.get("debtToEquity"),
                "crescimento_receita": fin.get("revenueGrowth"),
                "crescimento_lucro": fin.get("earningsGrowth"),
            },
            "saude_financeira": {
                "receita_ttm": latest_dre.get("totalRevenue"),
                "lucro_liquido_ttm": latest_dre.get("netIncome"),
                "ebitda": latest_dre.get("ebitda"),
                "ativos_totais": latest_bs.get("totalAssets"),
                "caixa": latest_bs.get("cash"),
                "divida_longo_prazo": latest_bs.get("longTermDebt"),
            },
            "dividendos": {
                "total_12_meses": round(total_divs_12m, 4),
                "dividend_yield": stats.get("dividendYield"),
                "frequencia": "Mensal" if len(cash_divs) > 11 else "Outro",
                "proximo_pagamento": proximo_pagamento,
                "ultimos": [
                    {
                        "data": d.get("paymentDate", "")[:10],
                        "valor": d.get("rate"),
                        "tipo": d.get("label"),
                    }
                    for d in divs_ordenados[:6]
                ],
            },
        }

    def _calculate_returns(self, hist_data: list[dict]) -> dict:
        """Calcula retornos percentuais para diferentes períodos."""
        if not hist_data:
            return {"1m": None, "6m": None, "1y": None}

        closes = [c.get("close", 0) for c in hist_data if c.get("close")]
        if len(closes) < 2:
            return {"1m": None, "6m": None, "1y": None}

        latest = closes[-1]
        result = {}

        for period_days, key in [(21, "1m"), (126, "6m"), (252, "1y")]:
            if len(closes) > period_days:
                past = closes[-(period_days + 1)]
                result[key] = round(((latest - past) / past) * 100, 2)
            else:
                result[key] = None

        return result
