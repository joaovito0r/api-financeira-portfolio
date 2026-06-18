"""
Rota de análise comparativa entre ativos.

Compara dois ou mais ativos lado a lado com métricas-chave.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.validation import normalize_ticker

router = APIRouter(tags=["Comparação"])


@router.get(
    "/compare",
    summary="Comparar ativos",
    description=(
        "Compara dois ou mais ativos lado a lado com métricas "
        "como P/L, P/VP, DY, ROE, EV/EBITDA, etc."
    ),
)
async def compare(
    request: Request,
    tickers: str = Query(
        ..., description="Tickers separados por vírgula (ex: PETR4,VALE3)"
    ),
) -> dict[str, Any]:
    """Compara múltiplos ativos com métricas fundamentalistas."""
    try:
        ticker_list = [
            normalize_ticker(t) for t in tickers.split(",") if t.strip()
        ]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if len(ticker_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="Informe pelo menos 2 tickers para comparar",
        )

    brapi = request.app.state.brapi_client
    results = []

    for ticker in ticker_list:
        # Busca cotação
        quote_raw = await brapi.quote(ticker)
        quote = quote_raw.get("results", [{}])[0]

        # Busca indicadores
        fin_raw = await brapi.quote(ticker, modules="financialData")
        fin_data = fin_raw.get("results", [{}])[0].get("financialData", {})

        # Busca estatísticas
        stats_raw = await brapi.quote(ticker, modules="defaultKeyStatistics")
        stats_data = stats_raw.get("results", [{}])[0].get("defaultKeyStatistics", {})

        # Busca perfil
        prof_raw = await brapi.quote(ticker, modules="summaryProfile")
        profile = prof_raw.get("results", [{}])[0].get("summaryProfile", {})

        results.append(
            {
                "ticker": ticker,
                "name": quote.get("longName", quote.get("shortName", "")),
                "price": quote.get("regularMarketPrice"),
                "change_percent": quote.get("regularMarketChangePercent"),
                "market_cap": quote.get("marketCap"),
                "sector": profile.get("sector"),
                "industry": profile.get("industry"),
                "pl": stats_data.get("trailingPE"),
                "pvp": stats_data.get("priceToBook"),
                "ev_ebitda": stats_data.get("enterpriseToEbitda"),
                "dividend_yield": stats_data.get("dividendYield"),
                "roe": fin_data.get("returnOnEquity"),
                "roa": fin_data.get("returnOnAssets"),
                "margem_liquida": fin_data.get("profitMargins"),
                "beta": stats_data.get("beta"),
                "vpa": stats_data.get("bookValue"),
                "lpa": stats_data.get("earningsPerShare"),
                "preco_alvo": fin_data.get("targetMeanPrice"),
                "recomendacao": fin_data.get("recommendationKey"),
            }
        )

    return {"tickers": results, "total": len(results)}
