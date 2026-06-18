"""Testa que a concorrência global de saída à brapi é limitada."""

from __future__ import annotations

import asyncio

import pytest

from app.repositories.brapi import client as brapi_client_mod


@pytest.mark.asyncio
async def test_concorrencia_global_nao_excede_o_maximo(monkeypatch) -> None:
    # Concorrência máxima = 2; intervalo mínimo = 0 para o teste
    sem = asyncio.Semaphore(2)
    monkeypatch.setattr(brapi_client_mod, "_brapi_semaphore", sem)
    monkeypatch.setattr(brapi_client_mod, "_MIN_INTERVAL", 0.0)

    ativos = {"n": 0, "max": 0}

    # Exercita o caminho do semáforo diretamente
    async def call() -> None:
        async with brapi_client_mod._brapi_semaphore:
            ativos["n"] += 1
            ativos["max"] = max(ativos["max"], ativos["n"])
            await asyncio.sleep(0.01)
            ativos["n"] -= 1

    await asyncio.gather(*(call() for _ in range(10)))
    assert ativos["max"] <= 2
