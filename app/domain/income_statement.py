"""
Entidade de domínio: DRE (IncomeStatement).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class IncomeStatement:
    """Demonstrativo de Resultados do Exercício.

    Attributes:
        ticker: Código do ativo.
        end_date: Data da demonstração.
        total_revenue: Receita líquida.
        cost_of_revenue: Custo dos produtos.
        gross_profit: Lucro bruto.
        operating_income: Resultado operacional.
        net_income: Lucro líquido.
        ebitda: EBITDA.
    """

    ticker: str
    end_date: date
    total_revenue: float
    cost_of_revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    ebitda: float | None = None
