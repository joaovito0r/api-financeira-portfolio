"""
Testes do helper de concorrência limitada (gather_limited).
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.concurrency import gather_limited


@pytest.mark.asyncio
async def test_preserva_ordem_dos_resultados() -> None:
    """Os resultados devem sair na mesma ordem das corrotinas, não de conclusão."""

    async def echo(value: int, delay: float) -> int:
        await asyncio.sleep(delay)
        return value

    # O primeiro demora mais que o segundo; a ordem do resultado deve ser estável.
    resultado = await gather_limited(echo(1, 0.03), echo(2, 0.01), echo(3, 0.0))
    assert resultado == [1, 2, 3]


@pytest.mark.asyncio
async def test_respeita_limite_de_concorrencia() -> None:
    """Nunca deve haver mais que `limit` corrotinas executando ao mesmo tempo."""
    em_execucao = 0
    pico = 0

    async def tarefa() -> None:
        nonlocal em_execucao, pico
        em_execucao += 1
        pico = max(pico, em_execucao)
        await asyncio.sleep(0.01)
        em_execucao -= 1

    await gather_limited(*(tarefa() for _ in range(10)), limit=3)
    assert pico <= 3


@pytest.mark.asyncio
async def test_lista_vazia() -> None:
    """Sem corrotinas, retorna lista vazia."""
    assert await gather_limited() == []
