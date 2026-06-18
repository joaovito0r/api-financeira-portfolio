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
