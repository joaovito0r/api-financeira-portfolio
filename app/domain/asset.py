"""
Entidade de domínio: Ativo (Asset).

Representa um ativo financeiro negociado na B3.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    """Ativo financeiro (ação, FII, ETF, BDR, índice).

    Attributes:
        ticker: Código único do ativo (ex: PETR4).
        name: Nome do ativo.
        type: Tipo (stock, fund, etf, bdr, index).
        sector: Setor de atuação.
        logo: URL do logo.
    """

    ticker: str
    name: str
    type: str = "stock"
    sector: str | None = None
    logo: str | None = None
