"""
Entidade de domínio: Preço Histórico (OHLCV).

Série temporal de preços para gráficos de candle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OHLCV:
    """Preço histórico de um ativo em uma data.

    Attributes:
        ticker: Código do ativo.
        date: Data do pregão.
        open: Preço de abertura.
        high: Preço máximo.
        low: Preço mínimo.
        close: Preço de fechamento.
        volume: Volume negociado.
    """

    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
