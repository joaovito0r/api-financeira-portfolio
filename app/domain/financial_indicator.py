"""
Entidade de domínio: Indicadores Financeiros (FinancialIndicator).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinancialIndicator:
    """Múltiplos e indicadores de valuation.

    Attributes:
        ticker: Código do ativo.
        current_price: Preço atual.
        target_price: Preço-alvo médio.
        recommendation: buy, hold, sell.
        gross_margin: Margem bruta.
        operating_margin: Margem operacional.
        profit_margin: Margem líquida.
        roe: Retorno sobre Patrimônio Líquido.
        roa: Retorno sobre Ativos.
        revenue_growth: Crescimento da receita.
        earnings_growth: Crescimento do lucro.
        debt_to_equity: Dívida / PL.
    """

    ticker: str
    current_price: float | None = None
    target_price: float | None = None
    recommendation: str | None = None  # buy | hold | sell
    gross_margin: float | None = None
    operating_margin: float | None = None
    profit_margin: float | None = None
    roe: float | None = None
    roa: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    debt_to_equity: float | None = None
