"""
Entidade de domínio: Estatísticas-Chave (KeyStatistic).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyStatistic:
    """Métricas para análise fundamentalista.

    Attributes:
        ticker: Código do ativo.
        price_to_book: P/VP.
        forward_pe: P/L futuro.
        trailing_pe: P/L corrente.
        enterprise_value: Enterprise Value.
        ev_to_ebitda: EV/EBITDA.
        ev_to_revenue: EV/Receita.
        beta: Beta do ativo.
        dividend_yield: Dividend Yield.
        book_value: VPA.
        earnings_per_share: LPA.
        week_high_52: Máxima 52 semanas.
        week_low_52: Mínima 52 semanas.
    """

    ticker: str
    price_to_book: float | None = None
    forward_pe: float | None = None
    trailing_pe: float | None = None
    enterprise_value: float | None = None
    ev_to_ebitda: float | None = None
    ev_to_revenue: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    book_value: float | None = None
    earnings_per_share: float | None = None
    week_high_52: float | None = None
    week_low_52: float | None = None
