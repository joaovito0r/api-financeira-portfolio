"""
Schemas Pydantic para dividendos/proventos.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DividendResponse(BaseModel):
    """Resposta com provento de um ativo."""

    ticker: str = Field(..., description="Código do ativo")
    payment_date: date = Field(..., description="Data do pagamento")
    value: float = Field(..., description="Valor por cota")
    type: str = Field(..., description="Tipo: DIVIDENDO, JCP, BONIFICACAO")
    reference_date: date | None = Field(None, description="Data base")


class DividendListResponse(BaseModel):
    """Resposta com lista de proventos."""

    dividends: list[DividendResponse]
    total: int = Field(..., description="Total de proventos")
