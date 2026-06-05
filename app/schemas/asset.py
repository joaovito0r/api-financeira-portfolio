"""
Schemas Pydantic para ativos.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    """Resposta com dados de um ativo."""

    ticker: str = Field(..., description="Código do ativo")
    name: str = Field(..., description="Nome do ativo")
    type: str = Field(..., description="Tipo (stock, fund, etf, bdr, index)")
    sector: str | None = Field(None, description="Setor")
    logo: str | None = Field(None, description="URL do logo")


class AssetListResponse(BaseModel):
    """Resposta com listagem de ativos."""

    assets: list[AssetResponse]
    total: int = Field(..., description="Total de ativos encontrados")
