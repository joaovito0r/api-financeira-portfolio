"""
Entidade de domínio: Balanço Patrimonial (BalanceSheet).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BalanceSheet:
    """Balanço Patrimonial de uma empresa.

    Attributes:
        ticker: Código do ativo.
        end_date: Data do balanço.
        total_assets: Ativo total.
        current_assets: Ativo circulante.
        current_liabilities: Passivo circulante.
        shareholder_equity: Patrimônio líquido.
        long_term_debt: Dívida de longo prazo.
        cash: Caixa e equivalentes.
    """

    ticker: str
    end_date: date
    total_assets: float
    current_assets: float
    current_liabilities: float
    shareholder_equity: float
    long_term_debt: float | None = None
    cash: float | None = None
