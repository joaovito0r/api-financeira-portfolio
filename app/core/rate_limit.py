"""Rate limiting por token bucket, em memória.

Algoritmo clássico: cada balde repõe tokens continuamente até a capacidade;
cada requisição consome 1 token. Permite rajadas (burst) até a capacidade e
limita a taxa sustentada pela reposição.
"""

from __future__ import annotations

import time


class TokenBucket:
    """Balde de tokens com reposição contínua."""

    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = float(capacity)
        self.updated_at = time.monotonic()

    def _refill(self, now: float) -> None:
        elapsed = now - self.updated_at
        if elapsed > 0:
            self.tokens = min(
                float(self.capacity), self.tokens + elapsed * self.refill_per_sec
            )
            self.updated_at = now

    def try_consume(self, tokens: int = 1) -> bool:
        """Consome `tokens` se houver saldo; retorna se foi permitido."""
        self._refill(time.monotonic())
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def retry_after(self, tokens: int = 1) -> float:
        """Segundos estimados até haver `tokens` disponíveis."""
        self._refill(time.monotonic())
        deficit = tokens - self.tokens
        if deficit <= 0 or self.refill_per_sec <= 0:
            return 0.0 if deficit <= 0 else float("inf")
        return deficit / self.refill_per_sec


class RateLimiter:
    """Registry de baldes indexados por chave (`namespace:identidade`)."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def check(
        self, key: str, capacity: int, refill_per_sec: float
    ) -> tuple[bool, float]:
        """Tenta consumir 1 token do balde da chave.

        Retorna (permitido, retry_after_segundos).
        """
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(capacity, refill_per_sec)
            self._buckets[key] = bucket
        allowed = bucket.try_consume(1)
        retry = 0.0 if allowed else bucket.retry_after(1)
        return allowed, retry


limiter = RateLimiter()
"""Instância global (single-process)."""
