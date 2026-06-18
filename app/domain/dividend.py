"""
Entidade de domínio: Provento (Dividend).

Distribuição de lucros aos acionistas.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class Dividend:
    """Provento pago por um ativo.

    Attributes:
        ticker: Código do ativo.
        date: Data do pagamento.
        value: Valor por cota.
        type: Tipo (DIVIDENDO, JCP, BONIFICACAO).
        reference_date: Data base para o provento.
    """

    ticker: str
    date: datetime.date
    value: float
    type: str  # DIVIDENDO | JCP | BONIFICACAO
    reference_date: datetime.date | None = None
