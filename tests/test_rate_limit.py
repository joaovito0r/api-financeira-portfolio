"""Testes do token bucket e do RateLimiter."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import RateLimitError
from app.core.rate_limit import RateLimiter, TokenBucket


def test_bucket_permite_ate_capacidade_e_depois_nega() -> None:
    bucket = TokenBucket(capacity=3, refill_per_sec=0.0)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False  # esgotou


def test_bucket_refill_ao_longo_do_tempo(monkeypatch) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: clock["t"])
    bucket = TokenBucket(capacity=2, refill_per_sec=1.0)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False
    clock["t"] += 1.0  # repõe 1 token
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False


def test_retry_after_estima_segundos(monkeypatch) -> None:
    clock = {"t": 0.0}
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: clock["t"])
    bucket = TokenBucket(capacity=1, refill_per_sec=0.5)  # 1 token a cada 2s
    assert bucket.try_consume() is True
    assert bucket.retry_after() == 2.0


def test_limiter_isola_chaves(monkeypatch) -> None:
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: 0.0)
    limiter = RateLimiter()
    allowed_a, _ = limiter.check("auth:A", capacity=1, refill_per_sec=0.0)
    allowed_a2, _ = limiter.check("auth:A", capacity=1, refill_per_sec=0.0)
    allowed_b, _ = limiter.check("auth:B", capacity=1, refill_per_sec=0.0)
    assert allowed_a is True
    assert allowed_a2 is False  # A esgotou
    assert allowed_b is True  # B independente


def test_rate_limit_error_carrega_retry_e_limit() -> None:
    err = RateLimitError(retry_after=4.2, limit=60)
    assert err.retry_after == 4.2
    assert err.limit == 60


@pytest.mark.asyncio
async def test_login_excede_limite_publico_retorna_429(monkeypatch) -> None:
    # Zera o estado global do limiter entre execuções
    from app.core import rate_limit as rl

    rl.limiter._buckets.clear()
    monkeypatch.setattr(rl.settings, "rate_limit_enabled", True, raising=False)
    monkeypatch.setattr(rl.settings, "rate_limit_public_per_min", 2, raising=False)

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Credenciais inválidas de propósito: queremos só exercitar o limite.
        codes = []
        for _ in range(4):
            r = await c.post(
                "/auth/login", json={"email": "x@x.com", "password": "errada123"}
            )
            codes.append(r.status_code)
    assert 429 in codes  # após 2 tentativas, estoura


def test_limiter_aplica_teto_no_numero_de_baldes(monkeypatch) -> None:
    """Atacante rotacionando X-Forwarded-For não deve crescer o dict sem limite.

    Cada IP descartável faz só 1 request e nunca volta. Com refill rápido,
    pelo tempo em que o limiter atinge o teto e tenta inserir o próximo
    balde, os baldes anteriores já reabasteceram (tokens >= capacity) e são
    elegíveis à varredura — simulando o caso comum do ataque.
    """
    clock = {"t": 0.0}
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: clock["t"])
    limiter = RateLimiter(max_buckets=10)
    for i in range(1000):
        clock["t"] += 1.0  # tempo passa entre requests (refill_per_sec=1.0)
        limiter.check(f"auth:ip-{i}", capacity=1, refill_per_sec=1.0)
        assert len(limiter._buckets) <= 10


def test_limiter_nao_descarta_baldes_ativamente_limitados(monkeypatch) -> None:
    """Baldes esgotados (em uso real de limitação) não somem na eviction."""
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: 0.0)
    limiter = RateLimiter(max_buckets=3)
    # Esgota completamente o balde de "A" (fica com tokens=0, não está cheio).
    limiter.check("A", capacity=1, refill_per_sec=0.0)
    assert "A" in limiter._buckets

    # Preenche o limiter com baldes novos (cheios) até estourar o teto,
    # forçando a varredura de eviction.
    limiter.check("B", capacity=1, refill_per_sec=0.0)
    limiter.check("C", capacity=1, refill_per_sec=0.0)
    limiter.check("D", capacity=1, refill_per_sec=0.0)

    # "A" continua presente: estava esgotado (tokens=0 < capacity), não é
    # elegível para a varredura de baldes cheios.
    assert "A" in limiter._buckets


@pytest.mark.asyncio
async def test_handler_429_tem_retry_after_header() -> None:
    from fastapi import FastAPI

    from app.main import rate_limit_handler  # handler exportado

    app = FastAPI()

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RateLimitError(retry_after=3.0, limit=60)

    app.add_exception_handler(RateLimitError, rate_limit_handler)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/boom")
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "3"
    assert resp.headers["X-RateLimit-Limit"] == "60"
