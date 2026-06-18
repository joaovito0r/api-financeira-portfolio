"""
Rota de análise comparativa entre ativos.

Compara dois ou mais ativos lado a lado com métricas-chave.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import rate_limit_expensive
from app.core.concurrency import gather_limited
from app.core.validation import normalize_ticker

router = APIRouter(tags=["Comparação"])


@router.get(
    "/compare",
    summary="Comparar ativos",
    description=(
        "Compara dois ou mais ativos lado a lado com métricas "
        "como P/L, P/VP, DY, ROE, EV/EBITDA, etc."
    ),
    dependencies=[Depends(rate_limit_expensive)],
)
async def compare(
    request: Request,
    tickers: str = Query(
        ..., description="Tickers separados por vírgula (ex: PETR4,VALE3)"
    ),
) -> dict[str, Any]:
    """Compara múltiplos ativos com métricas fundamentalistas."""
    try:
        ticker_list = [normalize_ticker(t) for t in tickers.split(",") if t.strip()]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if len(ticker_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="Informe pelo menos 2 tickers para comparar",
        )

    brapi = request.app.state.brapi_client

    # As 4 chamadas por ticker (cotação, indicadores, estatísticas, perfil) são
    # independentes entre si e entre tickers; rodam todas em paralelo com
    # concorrência limitada para respeitar o rate limit do plano free.
    raw_results = await gather_limited(
        *(brapi.quote(ticker) for ticker in ticker_list),
        *(brapi.quote(ticker, modules="financialData") for ticker in ticker_list),
        *(
            brapi.quote(ticker, modules="defaultKeyStatistics")
            for ticker in ticker_list
        ),
        *(brapi.quote(ticker, modules="summaryProfile") for ticker in ticker_list),
    )
    n = len(ticker_list)
    quote_raws, fin_raws, stats_raws, prof_raws = (
        raw_results[:n],
        raw_results[n : 2 * n],
        raw_results[2 * n : 3 * n],
        raw_results[3 * n :],
    )

    results = []
    for ticker, quote_raw, fin_raw, stats_raw, prof_raw in zip(
        ticker_list, quote_raws, fin_raws, stats_raws, prof_raws, strict=True
    ):
        quote = quote_raw.get("results", [{}])[0]
        fin_data = fin_raw.get("results", [{}])[0].get("financialData", {})
        stats_data = stats_raw.get("results", [{}])[0].get("defaultKeyStatistics", {})
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
