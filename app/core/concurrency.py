"""
Utilitários de concorrência para chamadas externas.

Permite paralelizar requisições (ex: brapi.dev) com um limite de concorrência,
respeitando o rate limit do plano free e evitando HTTP 429.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

# Máximo de chamadas simultâneas ao brapi.dev. Conservador para o plano free.
BRAPI_MAX_CONCURRENCY = 4


async def gather_limited[T](
    *coros: Awaitable[T],
    limit: int = BRAPI_MAX_CONCURRENCY,
) -> list[T]:
    """Executa corrotinas em paralelo com concorrência limitada por semáforo.

    Args:
        coros: Corrotinas a executar.
        limit: Máximo de execuções simultâneas.

    Returns:
        Resultados na mesma ordem das corrotinas recebidas.
    """
    sem = asyncio.Semaphore(limit)

    async def _run(coro: Awaitable[T]) -> T:
        async with sem:
            return await coro

    return await asyncio.gather(*(_run(c) for c in coros))
