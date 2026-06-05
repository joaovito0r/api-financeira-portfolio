"""
Interface abstrata para repositórios de dados.

Define o contrato que qualquer fonte de dados (brapi.dev, banco local)
deve implementar. Segue o padrão Repository.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class AbstractRepository(ABC, Generic[T]):
    """Repositório genérico abstrato."""

    @abstractmethod
    async def get(self, identifier: str) -> T | None:
        """Busca um registro pelo identificador único."""
        ...

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Persiste uma entidade."""
        ...
