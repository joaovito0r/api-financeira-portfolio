"""Rate limiting por token bucket, em memória.

Algoritmo clássico: cada balde repõe tokens continuamente até a capacidade;
cada requisição consome 1 token. Permite rajadas (burst) até a capacidade e
limita a taxa sustentada pela reposição.
"""

from __future__ import annotations

import time

from app.config import settings  # noqa: F401  (reexport p/ testes/monkeypatch)


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
    """Registry de baldes indexados por chave (`namespace:identidade`).

    Como a chave normalmente deriva de algo controlável pelo cliente (ex.:
    IP via `X-Forwarded-For`, que é spoofável), um atacante rotacionando a
    chave a cada requisição criaria uma entrada nova por request, fazendo o
    dict `_buckets` crescer sem limite (DoS por exaustão de memória num
    processo de vida longa). Para evitar isso, o registry tem um teto
    (`max_buckets`): ao atingi-lo, baldes totalmente reabastecidos (cheios)
    são descartados antes de inserir um balde novo — ver `_evict_full`.
    """

    def __init__(self, max_buckets: int | None = None) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self.max_buckets = (
            max_buckets if max_buckets is not None else settings.rate_limit_max_buckets
        )

    def _evict_full(self) -> None:
        """Remove do registry todo balde já totalmente reabastecido.

        Um balde com `tokens >= capacity` é equivalente a um balde novo:
        descartá-lo não perde nenhum estado de limitação relevante, porque
        na próxima requisição dessa chave um balde novo seria criado com o
        mesmo efeito prático (cheio). Já baldes esgotados ou parcialmente
        consumidos (em uso ativo de limitação) são preservados.

        Antes de avaliar, repõe os tokens de cada balde (`_refill`) para não
        manter como "não cheio" um balde que já teria reabastecido até a
        capacidade pelo simples passar do tempo.
        """
        now = time.monotonic()
        cheios = []
        for chave, balde in self._buckets.items():
            balde._refill(now)
            if balde.tokens >= balde.capacity:
                cheios.append(chave)
        for chave in cheios:
            del self._buckets[chave]

    def check(
        self, key: str, capacity: int, refill_per_sec: float
    ) -> tuple[bool, float]:
        """Tenta consumir 1 token do balde da chave.

        Retorna (permitido, retry_after_segundos).
        """
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self.max_buckets:
                self._evict_full()
            # Caso comum de DoS (muitos IPs de 1 request cada) é varrido
            # acima. Se mesmo assim o teto persistir (todos os baldes estão
            # ativamente limitados), aceitamos o crescimento temporário em
            # vez de descartar estado de limitação de clientes legítimos.
            bucket = TokenBucket(capacity, refill_per_sec)
            self._buckets[key] = bucket
        allowed = bucket.try_consume(1)
        retry = 0.0 if allowed else bucket.retry_after(1)
        return allowed, retry


limiter = RateLimiter()
"""Instância global (single-process), com o cap default das settings."""
