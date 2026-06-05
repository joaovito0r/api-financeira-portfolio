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
    """Limite de requisições excedido."""
