"""
Schemas Pydantic para consulta de cotações.

Define os contratos de entrada (request) e saída (response)
da API para o endpoint de cotações.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    """Resposta com cotação de um ativo."""

    ticker: str = Field(..., description="Código do ativo")
    timestamp: datetime = Field(..., description="Data/hora da cotação")
    price: float = Field(..., description="Preço atual")
    change: float = Field(..., description="Variação absoluta")
    change_percent: float = Field(..., description="Variação percentual")
    day_high: float = Field(..., description="Máxima do dia")
    day_low: float = Field(..., description="Mínima do dia")
    volume: int = Field(..., description="Volume financeiro")
    open: float = Field(..., description="Abertura do dia")
    previous_close: float = Field(..., description="Fechamento anterior")
    market_cap: float | None = Field(None, description="Valor de mercado")


class QuoteListResponse(BaseModel):
    """Resposta com múltiplas cotações."""

    quotes: list[QuoteResponse]
    total: int = Field(..., description="Quantidade de cotações retornadas")
