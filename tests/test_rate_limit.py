"""Testes do token bucket e do RateLimiter."""

from __future__ import annotations

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
