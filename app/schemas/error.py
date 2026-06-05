"""
Schemas Pydantic para erros e mensagens genéricas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Resposta padrão para erros."""

    error: str = Field(..., description="Mensagem de erro")
    status_code: int = Field(..., description="Código HTTP")
