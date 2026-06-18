"""
Exceções personalizadas do domínio.

Erros tipados que podem ser lançados em qualquer camada
e capturados pelos handlers do FastAPI.
"""

from __future__ import annotations


class DomainError(Exception):
    """Erro base do domínio."""


class NotFoundError(DomainError):
    """Entidade não encontrada."""


class ExternalAPIError(DomainError):
    """Erro na API externa (brapi.dev)."""


class RateLimitError(DomainError):
    """Limite de requisições excedido (token bucket)."""

    def __init__(self, retry_after: float, limit: int) -> None:
        self.retry_after = retry_after
        self.limit = limit
        super().__init__("Limite de requisições excedido")
