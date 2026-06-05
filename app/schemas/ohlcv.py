"""
Schemas Pydantic para OHLCV (histórico de preços).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class OHLCVResponse(BaseModel):
    """Resposta com um candle OHLCV."""

    ticker: str = Field(..., description="Código do ativo")
    trade_date: date = Field(..., description="Data do pregão")
    open: float = Field(..., description="Preço de abertura")
    high: float = Field(..., description="Preço máximo")
    low: float = Field(..., description="Preço mínimo")
    close: float = Field(..., description="Preço de fechamento")
    volume: int = Field(..., description="Volume negociado")


class OHLCVListResponse(BaseModel):
    """Resposta com série histórica."""

    ticker: str = Field(..., description="Código do ativo")
    history: list[OHLCVResponse]
    total: int = Field(..., description="Quantidade de candles")
