"""
Entidade de domínio: Cotação (Quote).

Snapshot do preço de um ativo em tempo real.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    """Cotação em tempo real de um ativo.

    Attributes:
        ticker: Código do ativo.
        timestamp: Data/hora da última atualização.
        price: Preço atual.
        change: Variação absoluta.
        change_percent: Variação percentual.
        day_high: Máxima do dia.
        day_low: Mínima do dia.
        volume: Volume financeiro.
        open: Abertura do dia.
        previous_close: Fechamento anterior.
        market_cap: Valor de mercado.
    """

    ticker: str
    timestamp: datetime
    price: float
    change: float
    change_percent: float
    day_high: float
    day_low: float
    volume: int
    open: float
    previous_close: float
    market_cap: float | None = None
