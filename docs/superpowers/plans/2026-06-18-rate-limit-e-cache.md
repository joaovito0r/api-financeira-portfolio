# Rate Limiting + Cache Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar token bucket de entrada (por usuário/IP) e endurecer o cache de saída à brapi (plugar endpoints órfãos, TTL ciente do pregão, cache quente do universo observado, throttle global), respeitando a quota do plano free (15k/mês).

**Architecture:** Token bucket em memória exposto via dependências FastAPI que levantam `RateLimitError` → handler 429. Cache de saída ganha tabela genérica `cache_entries` para dados lentos, política ciente do pregão, task asyncio no `lifespan` que reaquece o universo observado, e um throttle global (semáforo + intervalo mínimo) no `BrapiClient`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async (aiosqlite), httpx, pydantic-settings, pytest/pytest-asyncio.

## Global Constraints

- Rodar ferramentas SEMPRE como módulo do venv: `.venv/bin/python -m pytest|ruff|mypy` (shebangs do venv estão quebrados; NÃO usar `.venv/bin/pytest` direto).
- Ao final de cada task: `.venv/bin/python -m ruff check app tests` = 0, `.venv/bin/python -m mypy app` = `Success`, `.venv/bin/python -m pytest -q` verde.
- `from __future__ import annotations` no topo de todo módulo novo (padrão do projeto).
- Tipagem estrita (mypy strict já ligado): anotar tudo, sem `Any` solto onde puder ser específico.
- Comentários/docstrings em português (padrão do projeto).
- Orçamento brapi free: 15.000 req/mês; cache quente respeita `N/T ≤ ~1,7` (tickers / minutos de intervalo).
- NÃO commitar com `&`/disown ao subir servidor; usar tool de background.

---

### Task 1: TokenBucket + RateLimiter (núcleo, lógica pura)

**Files:**
- Create: `app/core/rate_limit.py`
- Test: `tests/test_rate_limit.py`

**Interfaces:**
- Produces:
  - `class TokenBucket` com `__init__(self, capacity: int, refill_per_sec: float)`, `try_consume(self, tokens: int = 1) -> bool`, `retry_after(self, tokens: int = 1) -> float`
  - `class RateLimiter` com `check(self, key: str, capacity: int, refill_per_sec: float) -> tuple[bool, float]`
  - `limiter: RateLimiter` (instância global do módulo)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rate_limit.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.rate_limit'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/rate_limit.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Lint/type + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app
git add app/core/rate_limit.py tests/test_rate_limit.py
git commit -m "feat(rate-limit): TokenBucket e RateLimiter em memória

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Config + RateLimitError com retry_after + handler 429

**Files:**
- Modify: `app/config.py` (adicionar settings de rate limit)
- Modify: `app/core/exceptions.py:23-24` (`RateLimitError` ganha atributos)
- Modify: `app/main.py` (registrar handler de `RateLimitError`)
- Test: `tests/test_rate_limit.py` (adicionar teste do handler via app)

**Interfaces:**
- Consumes: `RateLimiter.check` (Task 1)
- Produces:
  - `RateLimitError(retry_after: float, limit: int)` com `.retry_after`, `.limit`
  - Settings: `rate_limit_enabled: bool`, `rate_limit_auth_per_min: int`, `rate_limit_auth_burst: int`, `rate_limit_public_per_min: int`, `rate_limit_data_per_min: int`, `rate_limit_data_burst: int`, `rate_limit_expensive_per_min: int`

- [ ] **Step 1: Write the failing test**

```python
# adicionar em tests/test_rate_limit.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import RateLimitError


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -q`
Expected: FAIL (`TypeError` no construtor de `RateLimitError` / `ImportError` de `rate_limit_handler`)

- [ ] **Step 3a: Atualizar `RateLimitError`**

Substituir em `app/core/exceptions.py` o bloco:

```python
class RateLimitError(DomainError):
    """Limite de requisições excedido."""
```

por:

```python
class RateLimitError(DomainError):
    """Limite de requisições excedido (token bucket)."""

    def __init__(self, retry_after: float, limit: int) -> None:
        self.retry_after = retry_after
        self.limit = limit
        super().__init__("Limite de requisições excedido")
```

- [ ] **Step 3b: Adicionar settings em `app/config.py`**

Inserir após o bloco `# Cache` (linha 37):

```python
    # Rate limiting (token bucket em memória)
    rate_limit_enabled: bool = True
    rate_limit_auth_per_min: int = 60
    rate_limit_auth_burst: int = 100
    rate_limit_public_per_min: int = 10
    rate_limit_data_per_min: int = 60
    rate_limit_data_burst: int = 100
    rate_limit_expensive_per_min: int = 10
```

- [ ] **Step 3c: Registrar handler em `app/main.py`**

Adicionar `import math` no topo (após `import os`) e, na seção de handlers (após `validation_error_handler`), inserir:

```python
@app.exception_handler(RateLimitError)
async def rate_limit_handler(
    _request: Request, exc: RateLimitError
) -> JSONResponse:
    """Responde 429 com Retry-After quando o token bucket é excedido."""
    retry = max(1, math.ceil(exc.retry_after)) if exc.retry_after != float("inf") else 60
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Limite de requisições excedido. Tente novamente em instantes."
        },
        headers={
            "Retry-After": str(retry),
            "X-RateLimit-Limit": str(exc.limit),
        },
    )
```

Adicionar o import no topo de `app/main.py`:

```python
from app.core.exceptions import RateLimitError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -q`
Expected: PASS

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/config.py app/core/exceptions.py app/main.py tests/test_rate_limit.py
git commit -m "feat(rate-limit): config, RateLimitError com retry_after e handler 429

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Dependências FastAPI de rate limit + aplicar nas rotas

**Files:**
- Modify: `app/api/deps.py` (4 dependências)
- Modify: `app/api/routes/auth.py`, `compare.py`, `reports.py`, `quotes.py`, `fundamental.py`, `assets.py`, `dividends.py`, `watchlists.py`, `alerts.py`
- Test: `tests/test_rate_limit.py` (integração: estourar `public` no login)

**Interfaces:**
- Consumes: `limiter` (Task 1), settings + `RateLimitError` (Task 2), `get_current_user` (`deps.py:52`)
- Produces (em `app/api/deps.py`):
  - `def _client_ip(request: Request) -> str`
  - `async def rate_limit_login(request: Request) -> None` (IP, `public_per_min`)
  - `async def rate_limit_data(request: Request) -> None` (IP, `data_per_min`/`data_burst`)
  - `async def rate_limit_expensive(request: Request) -> None` (IP, `expensive_per_min`)
  - `async def rate_limit_user(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]`

> **Nota de planejamento:** `/compare`, `/reports`, `/quotes`, fundamentos e dividendos são rotas **públicas** (sem auth) hoje. Por isso os baldes "data" e "expensive" chaveiam por **IP**, não por `user_id`. `rate_limit_user` (chave `user_id`) aplica-se às rotas autenticadas (watchlists, alerts, `/auth/me`). Isso refina a spec, que assumia `user_id` para os caros.

- [ ] **Step 1: Write the failing test**

```python
# adicionar em tests/test_rate_limit.py
@pytest.mark.asyncio
async def test_login_excede_limite_publico_retorna_429(monkeypatch) -> None:
    # Zera o estado global do limiter entre execuções
    from app.core import rate_limit as rl

    rl.limiter._buckets.clear()
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
```

> Nota: `settings` precisa estar importado em `app/core/rate_limit.py` para o monkeypatch acima. Importe-o no Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py::test_login_excede_limite_publico_retorna_429 -q`
Expected: FAIL (nenhum 429 — limite ainda não aplicado)

- [ ] **Step 3: Implementar dependências em `app/api/deps.py`**

Adicionar imports no topo:

```python
from app.config import settings
from app.core.exceptions import RateLimitError
from app.core.rate_limit import limiter
```

Adicionar uma seção nova (após `valid_ticker`):

```python
# ── Rate limiting ──────────────────────────────────────


def _client_ip(request: Request) -> str:
    """IP de origem, respeitando X-Forwarded-For atrás de proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce(key: str, capacity: int, per_min: int) -> None:
    if not settings.rate_limit_enabled:
        return
    allowed, retry = limiter.check(key, capacity, per_min / 60)
    if not allowed:
        raise RateLimitError(retry_after=retry, limit=per_min)


async def rate_limit_login(request: Request) -> None:
    """Limite estrito por IP para login/registro (anti brute-force)."""
    _enforce(
        f"login:{_client_ip(request)}",
        settings.rate_limit_public_per_min,
        settings.rate_limit_public_per_min,
    )


async def rate_limit_data(request: Request) -> None:
    """Limite geral por IP para rotas públicas de dados leves."""
    _enforce(
        f"data:{_client_ip(request)}",
        settings.rate_limit_data_burst,
        settings.rate_limit_data_per_min,
    )


async def rate_limit_expensive(request: Request) -> None:
    """Limite apertado por IP para endpoints que fazem fan-out na brapi."""
    _enforce(
        f"expensive:{_client_ip(request)}",
        settings.rate_limit_expensive_per_min,
        settings.rate_limit_expensive_per_min,
    )


async def rate_limit_user(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Limite por usuário autenticado; substitui get_current_user nas rotas."""
    _enforce(
        f"user:{user['id']}",
        settings.rate_limit_auth_burst,
        settings.rate_limit_auth_per_min,
    )
    return user
```

- [ ] **Step 3b: Importar `settings` em `app/core/rate_limit.py`**

Adicionar (para o monkeypatch do teste e uso futuro):

```python
from app.config import settings  # noqa: F401  (reexport p/ testes/monkeypatch)
```

- [ ] **Step 3c: Aplicar nas rotas**

Em cada rota, adicionar a dependência como efeito colateral via `dependencies=[...]` no decorator (não polui a assinatura):

- `app/api/routes/auth.py` — nas rotas de **login** e **registro**:
  ```python
  from fastapi import Depends
  from app.api.deps import rate_limit_login
  # no decorator de cada rota:
  @router.post("/login", dependencies=[Depends(rate_limit_login)], ...)
  @router.post("/register", dependencies=[Depends(rate_limit_login)], ...)
  ```
- `app/api/routes/compare.py` e `reports.py` — `dependencies=[Depends(rate_limit_expensive)]` no decorator.
- `app/api/routes/quotes.py` — rota `/quotes` (múltiplos): `rate_limit_expensive`; rotas `/quote/{ticker}` e `/quote/{ticker}/history`: `rate_limit_data`.
- `app/api/routes/fundamental.py`, `assets.py`, `dividends.py` — `rate_limit_data` em cada rota.
- `app/api/routes/watchlists.py`, `alerts.py` e **`auth.py` (rota `/me`)** — onde hoje usam `Depends(get_current_user)` na assinatura, **trocar por** `Depends(rate_limit_user)` (mesmo retorno `dict`, agora com limite por usuário).

Import necessário em cada arquivo de rota: `from app.api.deps import rate_limit_data` (ou o nome aplicável).

- [ ] **Step 4: Run test + suíte**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -q && .venv/bin/python -m pytest -q`
Expected: PASS (novo teste verde; suíte inteira verde — as fixtures de teste usam IPs/usuários estáveis, e os limites default (60/10) são altos o bastante para não estourar os testes existentes. Se algum teste de watchlist/alert fizer muitas chamadas, ajustar `rate_limit_enabled=False` na fixture `setup_app` do conftest.)

> Se a suíte existente estourar limite: em `tests/conftest.py`, dentro de `setup_app`, adicionar `from app.config import settings as _s; _s.rate_limit_enabled = False` e religar nos testes específicos de rate limit via monkeypatch (`rl.settings.rate_limit_enabled = True`). Documentar a escolha no commit.

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/api/deps.py app/core/rate_limit.py app/api/routes tests/test_rate_limit.py tests/conftest.py
git commit -m "feat(rate-limit): dependencias por IP/usuario aplicadas nas rotas (429)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Tabela genérica `cache_entries` + GenericCacheRepository

**Files:**
- Modify: `app/repositories/local/models.py` (novo `CacheEntryModel`)
- Create: `app/repositories/local/cache_repo.py`
- Modify: `app/core/cache.py` (adicionar `ASSET_LIST_CACHE`)
- Test: `tests/test_cache.py`

**Interfaces:**
- Consumes: `CachePolicy` (`app/core/cache.py`), `get_session` (`models.py:215`)
- Produces:
  - `CacheEntryModel` (tabela `cache_entries`: `key` PK, `payload` Text JSON, `policy` str, `cached_at` DateTime)
  - `class GenericCacheRepository` com `async get(self, key: str, policy: CachePolicy) -> Any | None` e `async save(self, key: str, value: Any, policy: CachePolicy) -> Any`
  - `ASSET_LIST_CACHE = CachePolicy(ttl=86400)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cache.py
"""Testes do cache genérico (cache_entries)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.cache import CachePolicy
from app.repositories.local.cache_repo import GenericCacheRepository
from app.repositories.local.models import init_db


@pytest.mark.asyncio
async def test_save_e_get_roundtrip() -> None:
    await init_db()
    repo = GenericCacheRepository()
    policy = CachePolicy(ttl=3600)
    await repo.save("profile:PETR4", {"sector": "Energia"}, policy)
    got = await repo.get("profile:PETR4", policy)
    assert got == {"sector": "Energia"}


@pytest.mark.asyncio
async def test_get_retorna_none_quando_expirado() -> None:
    await init_db()
    repo = GenericCacheRepository()
    expired = CachePolicy(ttl=1)
    await repo.save("k:expira", {"v": 1}, expired)
    # Força expiração reescrevendo cached_at no passado
    from sqlalchemy import select

    from app.repositories.local.models import CacheEntryModel, get_session

    async with get_session() as session:
        row = (
            await session.execute(
                select(CacheEntryModel).where(CacheEntryModel.key == "k:expira")
            )
        ).scalars().first()
        assert row is not None
        row.cached_at = datetime.now() - timedelta(seconds=10)
        await session.commit()
    assert await repo.get("k:expira", expired) is None


@pytest.mark.asyncio
async def test_save_sobrescreve_mesma_chave() -> None:
    await init_db()
    repo = GenericCacheRepository()
    policy = CachePolicy(ttl=3600)
    await repo.save("k:dup", {"v": 1}, policy)
    await repo.save("k:dup", {"v": 2}, policy)
    assert await repo.get("k:dup", policy) == {"v": 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cache.py -q`
Expected: FAIL (`ModuleNotFoundError: app.repositories.local.cache_repo`)

- [ ] **Step 3a: Adicionar `CacheEntryModel` em `app/repositories/local/models.py`**

Inserir após `DividendModel` (antes da seção `# ── Usuários`):

```python
class CacheEntryModel(Base):
    """Cache genérico chave→JSON para dados lentos (fundamentos, listas)."""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    policy: Mapped[str] = mapped_column(String(50), default="")
    cached_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )
```

- [ ] **Step 3b: Criar `app/repositories/local/cache_repo.py`**

```python
"""Repositório de cache genérico (tabela cache_entries).

Armazena qualquer payload serializável em JSON, indexado por chave, com
expiração definida por uma CachePolicy passada na leitura/escrita.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.cache import CachePolicy
from app.repositories.local.models import CacheEntryModel, get_session


class GenericCacheRepository:
    """Cache chave→JSON em SQLite, com política de expiração por chamada."""

    async def get(self, key: str, policy: CachePolicy) -> Any | None:
        """Retorna o valor cacheado ou None se ausente/expirado."""
        async with get_session() as session:
            row = (
                await session.execute(
                    select(CacheEntryModel).where(CacheEntryModel.key == key)
                )
            ).scalars().first()
            if row is None or policy.is_expired(row.cached_at):
                return None
            return json.loads(row.payload)

    async def save(self, key: str, value: Any, policy: CachePolicy) -> Any:
        """Persiste (ou sobrescreve) o valor sob a chave e retorna o valor."""
        payload = json.dumps(value, default=str, ensure_ascii=False)
        async with get_session() as session:
            row = (
                await session.execute(
                    select(CacheEntryModel).where(CacheEntryModel.key == key)
                )
            ).scalars().first()
            if row is None:
                session.add(
                    CacheEntryModel(
                        key=key,
                        payload=payload,
                        policy=str(policy.ttl),
                        cached_at=datetime.now(),
                    )
                )
            else:
                row.payload = payload
                row.cached_at = datetime.now()
            await session.commit()
        return value
```

- [ ] **Step 3c: Adicionar política em `app/core/cache.py`**

Inserir após `STATISTIC_CACHE`:

```python
ASSET_LIST_CACHE = CachePolicy(ttl=86400)  # 24h — lista de ativos muda raro
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cache.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/repositories/local/models.py app/repositories/local/cache_repo.py app/core/cache.py tests/test_cache.py
git commit -m "feat(cache): tabela generica cache_entries + GenericCacheRepository

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Plugar fundamentos no cache

**Files:**
- Modify: `app/services/fundamental_service.py` (injetar cache, cache-first)
- Modify: `app/api/routes/fundamental.py:17-18` (`get_fundamental_service` injeta cache repo)
- Test: `tests/test_cache.py` (adicionar testes de wiring)

**Interfaces:**
- Consumes: `GenericCacheRepository` (Task 4), políticas `PROFILE_CACHE`, `BALANCE_SHEET_CACHE`, `INDICATOR_CACHE`, `STATISTIC_CACHE`
- Produces: `FundamentalService.__init__(self, brapi_client: BrapiClient, cache_repo: GenericCacheRepository)`

- [ ] **Step 1: Write the failing test**

```python
# adicionar em tests/test_cache.py
from unittest.mock import AsyncMock

from app.core.cache import PROFILE_CACHE
from app.services.fundamental_service import FundamentalService


@pytest.mark.asyncio
async def test_fundamental_usa_cache_no_segundo_acesso() -> None:
    await init_db()
    brapi = AsyncMock()
    brapi.quote = AsyncMock(
        return_value={"results": [{"summaryProfile": {"sector": "Energia"}}]}
    )
    repo = GenericCacheRepository()
    # Limpa chave para teste determinístico
    from sqlalchemy import delete

    from app.repositories.local.models import CacheEntryModel, get_session

    async with get_session() as session:
        await session.execute(
            delete(CacheEntryModel).where(CacheEntryModel.key == "profile:PETR4")
        )
        await session.commit()

    service = FundamentalService(brapi_client=brapi, cache_repo=repo)
    first = await service.get_profile("PETR4")
    second = await service.get_profile("PETR4")

    assert first["sector"] == "Energia"
    assert second["sector"] == "Energia"
    brapi.quote.assert_awaited_once()  # 2º acesso veio do cache
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cache.py::test_fundamental_usa_cache_no_segundo_acesso -q`
Expected: FAIL (`TypeError`: `__init__` não aceita `cache_repo`)

- [ ] **Step 3a: Reescrever `FundamentalService` com cache-first**

Substituir `__init__` e os cinco métodos para usar cache. Construtor:

```python
    def __init__(
        self, brapi_client: BrapiClient, cache_repo: GenericCacheRepository
    ) -> None:
        self._brapi = brapi_client
        self._cache = cache_repo
```

Adicionar imports no topo:

```python
from app.core.cache import (
    BALANCE_SHEET_CACHE,
    INDICATOR_CACHE,
    PROFILE_CACHE,
    STATISTIC_CACHE,
)
from app.repositories.local.cache_repo import GenericCacheRepository
```

Envolver cada método no padrão cache-first. Exemplo para `get_profile` (aplicar o mesmo padrão aos demais com a política e chave correspondentes — `balance:{t}`/`BALANCE_SHEET_CACHE`, `income:{t}`/`BALANCE_SHEET_CACHE`, `indicators:{t}`/`INDICATOR_CACHE`, `statistics:{t}`/`STATISTIC_CACHE`):

```python
    async def get_profile(self, ticker: str) -> dict[str, Any]:
        """Perfil da empresa (cache-first)."""
        key = f"profile:{ticker.upper()}"
        cached = await self._cache.get(key, PROFILE_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        raw = await self._brapi.quote(ticker, modules="summaryProfile")
        profile = raw.get("results", [{}])[0].get("summaryProfile", {})
        result = {
            "ticker": ticker.upper(),
            "address": profile.get("address1"),
            "city": profile.get("city"),
            "state": profile.get("state"),
            "country": profile.get("country"),
            "website": profile.get("website"),
            "industry": profile.get("industry"),
            "sector": profile.get("sector"),
            "description": profile.get("longBusinessSummary"),
            "employees": profile.get("fullTimeEmployees"),
        }
        return await self._cache.save(key, result, PROFILE_CACHE)  # type: ignore[no-any-return]
```

> Para `get_balance_sheet` e `get_income_statement` (retornam `list[...]`), o tipo de retorno do cache é a própria lista; manter a anotação `list[dict[str, Any]]` e o `cast`/`type: ignore[no-any-return]` no `return` do cache. Use chaves `balance:{t}` e `income:{t}`.

- [ ] **Step 3b: Injetar cache repo na rota**

Em `app/api/routes/fundamental.py`, atualizar a factory:

```python
from app.repositories.local.cache_repo import GenericCacheRepository


def get_fundamental_service(request: Request) -> FundamentalService:
    return FundamentalService(
        brapi_client=request.app.state.brapi_client,
        cache_repo=GenericCacheRepository(),
    )
```

- [ ] **Step 4: Run test + suíte**

Run: `.venv/bin/python -m pytest tests/test_cache.py -q && .venv/bin/python -m pytest -q`
Expected: PASS (novo teste + suíte verdes)

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/services/fundamental_service.py app/api/routes/fundamental.py tests/test_cache.py
git commit -m "feat(cache): fundamentos (profile/bp/dre/indicadores/estatisticas) cache-first

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Plugar lista de ativos no cache

**Files:**
- Modify: `app/services/asset_service.py` (injetar cache, cache-first)
- Modify: `app/api/routes/assets.py` (factory injeta cache repo)
- Test: `tests/test_cache.py` (teste de wiring da lista)

**Interfaces:**
- Consumes: `GenericCacheRepository` (Task 4), `ASSET_LIST_CACHE` (Task 4)
- Produces: `AssetService.__init__(self, brapi_client: BrapiClient, cache_repo: GenericCacheRepository)`

- [ ] **Step 1: Write the failing test**

```python
# adicionar em tests/test_cache.py
from app.core.cache import ASSET_LIST_CACHE  # noqa: F401 (garante import válido)
from app.services.asset_service import AssetService


@pytest.mark.asyncio
async def test_lista_ativos_usa_cache() -> None:
    await init_db()
    brapi = AsyncMock()
    brapi.list_assets = AsyncMock(
        return_value={"stocks": [{"stock": "PETR4", "name": "Petrobras"}]}
    )
    from sqlalchemy import delete

    from app.repositories.local.models import CacheEntryModel, get_session

    async with get_session() as session:
        await session.execute(
            delete(CacheEntryModel).where(CacheEntryModel.key == "assets:all::")
        )
        await session.commit()

    service = AssetService(brapi_client=brapi, cache_repo=GenericCacheRepository())
    await service.list_assets()
    await service.list_assets()
    brapi.list_assets.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cache.py::test_lista_ativos_usa_cache -q`
Expected: FAIL (`TypeError` no construtor)

- [ ] **Step 3a: Reescrever `AssetService` cache-first**

```python
from app.core.cache import ASSET_LIST_CACHE
from app.repositories.local.cache_repo import GenericCacheRepository


class AssetService:
    """Serviço de consulta de ativos disponíveis (cache-first)."""

    def __init__(
        self, brapi_client: BrapiClient, cache_repo: GenericCacheRepository
    ) -> None:
        self._brapi = brapi_client
        self._cache = cache_repo

    async def list_assets(
        self, search: str | None = None, sector: str | None = None
    ) -> list[dict[str, Any]]:
        """Lista ativos disponíveis com filtros (cache por combinação de filtro)."""
        key = f"assets:all:{search or ''}:{sector or ''}"
        cached = await self._cache.get(key, ASSET_LIST_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        raw = await self._brapi.list_assets(search=search, sector=sector)
        stocks = raw.get("stocks", [])
        result = [
            {
                "ticker": s.get("stock", ""),
                "name": s.get("name", ""),
                "type": s.get("type", "stock"),
                "sector": s.get("sector"),
                "logo": s.get("logo"),
            }
            for s in stocks
        ]
        return await self._cache.save(key, result, ASSET_LIST_CACHE)  # type: ignore[no-any-return]

    async def available(self) -> list[dict[str, Any]]:
        """Lista simplificada de ativos (cache-first)."""
        key = "assets:available"
        cached = await self._cache.get(key, ASSET_LIST_CACHE)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        raw = await self._brapi.available()
        symbols = raw.get("symbols", [])
        result = [
            {"ticker": s.get("symbol", ""), "name": s.get("name", "")}
            for s in symbols
        ]
        return await self._cache.save(key, result, ASSET_LIST_CACHE)  # type: ignore[no-any-return]
```

- [ ] **Step 3b: Injetar cache na factory de `assets.py`**

Localizar a factory `get_asset_service` (ou equivalente) em `app/api/routes/assets.py` e injetar `cache_repo=GenericCacheRepository()`, importando `from app.repositories.local.cache_repo import GenericCacheRepository`. (Se a rota constrói `AssetService(brapi_client=...)` inline, adicionar o `cache_repo`.)

- [ ] **Step 4: Run test + suíte**

Run: `.venv/bin/python -m pytest tests/test_cache.py -q && .venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/services/asset_service.py app/api/routes/assets.py tests/test_cache.py
git commit -m "feat(cache): lista de ativos cache-first (TTL 24h)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Helper de pregão + TTL ciente do mercado

**Files:**
- Create: `app/core/market_hours.py`
- Modify: `app/core/cache.py` (`CachePolicy` ciente do pregão; `QUOTE_CACHE` market-aware)
- Test: `tests/test_market_hours.py`

**Interfaces:**
- Produces:
  - `def is_market_open(now: datetime | None = None) -> bool`
  - `CachePolicy` ganha `market_aware: bool = False`, `off_hours_ttl: int = 0`, método `effective_ttl(self) -> int`
- Consumes: nada externo novo.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_market_hours.py
"""Testes do helper de horário de pregão."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.market_hours import is_market_open

SP = ZoneInfo("America/Sao_Paulo")


def test_pregao_aberto_em_dia_util_meio_dia() -> None:
    assert is_market_open(datetime(2026, 6, 17, 12, 0, tzinfo=SP)) is True


def test_pregao_fechado_de_madrugada() -> None:
    assert is_market_open(datetime(2026, 6, 17, 3, 0, tzinfo=SP)) is False


def test_pregao_fechado_no_fim_de_semana() -> None:
    # 2026-06-20 é sábado
    assert is_market_open(datetime(2026, 6, 20, 12, 0, tzinfo=SP)) is False


def test_pregao_fechado_apos_as_17h() -> None:
    assert is_market_open(datetime(2026, 6, 17, 17, 30, tzinfo=SP)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_market_hours.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3a: Criar `app/core/market_hours.py`**

```python
"""Horário de pregão da B3 (sem feriados nesta versão)."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
MARKET_OPEN = time(10, 0)
MARKET_CLOSE = time(17, 0)


def is_market_open(now: datetime | None = None) -> bool:
    """True se o pregão regular está aberto (seg–sex, 10h–17h BRT).

    Feriados da B3 NÃO são considerados nesta versão (limitação conhecida).
    """
    moment = now or datetime.now(SAO_PAULO)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SAO_PAULO)
    else:
        moment = moment.astimezone(SAO_PAULO)
    if moment.weekday() >= 5:  # 5=sábado, 6=domingo
        return False
    return MARKET_OPEN <= moment.time() < MARKET_CLOSE
```

- [ ] **Step 3b: Tornar `CachePolicy` ciente do pregão**

Em `app/core/cache.py`, importar e estender:

```python
from app.core.market_hours import is_market_open
```

Atualizar a classe:

```python
class CachePolicy:
    def __init__(
        self,
        ttl: int = 0,
        perpetual: bool = False,
        market_aware: bool = False,
        off_hours_ttl: int = 0,
    ) -> None:
        self.ttl = ttl
        self.perpetual = perpetual
        self.market_aware = market_aware
        self.off_hours_ttl = off_hours_ttl

    def effective_ttl(self) -> int:
        """TTL efetivo: maior fora do pregão quando market_aware."""
        if self.market_aware and not is_market_open():
            return self.off_hours_ttl or self.ttl
        return self.ttl

    def is_expired(self, cached_at: datetime) -> bool:
        if self.perpetual:
            return False
        ttl = self.effective_ttl()
        if ttl <= 0:
            return True
        return datetime.now() - cached_at > timedelta(seconds=ttl)
```

E tornar a cotação ciente do mercado:

```python
QUOTE_CACHE = CachePolicy(ttl=900, market_aware=True, off_hours_ttl=21600)  # 15min / 6h
```

- [ ] **Step 4: Run test + suíte**

Run: `.venv/bin/python -m pytest tests/test_market_hours.py -q && .venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/core/market_hours.py app/core/cache.py tests/test_market_hours.py
git commit -m "feat(cache): TTL de cotacao ciente do pregao (15min no pregao, 6h fora)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Throttle global de saída na brapi

**Files:**
- Modify: `app/config.py` (`brapi_max_concurrency`, `brapi_min_interval_sec`)
- Modify: `app/repositories/brapi/client.py` (semáforo compartilhado + intervalo mínimo no `_get`)
- Modify: `app/core/concurrency.py` (`BRAPI_MAX_CONCURRENCY` lê de settings — opcional, manter compat)
- Test: `tests/test_brapi_throttle.py`

**Interfaces:**
- Consumes: settings
- Produces (em `app/repositories/brapi/client.py`, nível de módulo):
  - `_brapi_semaphore: asyncio.Semaphore`
  - `async def _throttle() -> None`
  - `_get` passa a adquirir o semáforo e aplicar o intervalo antes da chamada HTTP.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brapi_throttle.py
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

    async def fake_get(self, path, params=None):  # type: ignore[no-untyped-def]
        async with brapi_client_mod._brapi_semaphore:
            ativos["n"] += 1
            ativos["max"] = max(ativos["max"], ativos["n"])
            await asyncio.sleep(0.01)
            ativos["n"] -= 1
            return {"results": [{}]}

    # Exercita o caminho do semáforo diretamente
    async def call() -> None:
        async with brapi_client_mod._brapi_semaphore:
            ativos["n"] += 1
            ativos["max"] = max(ativos["max"], ativos["n"])
            await asyncio.sleep(0.01)
            ativos["n"] -= 1

    await asyncio.gather(*(call() for _ in range(10)))
    assert ativos["max"] <= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_brapi_throttle.py -q`
Expected: FAIL (`AttributeError`: módulo não tem `_brapi_semaphore`)

- [ ] **Step 3a: Settings em `app/config.py`**

Após o bloco de rate limiting, adicionar:

```python
    # Throttle de saída à brapi (protege a quota do plano free)
    brapi_max_concurrency: int = 4
    brapi_min_interval_sec: float = 0.0
```

- [ ] **Step 3b: Throttle em `app/repositories/brapi/client.py`**

Adicionar imports e primitivas de módulo (após os imports existentes):

```python
import asyncio
import time as _time

from app.config import settings

_brapi_semaphore = asyncio.Semaphore(settings.brapi_max_concurrency)
_MIN_INTERVAL = settings.brapi_min_interval_sec
_last_call_lock = asyncio.Lock()
_last_call_at = 0.0


async def _throttle() -> None:
    """Garante o intervalo mínimo global entre chamadas à brapi."""
    global _last_call_at
    if _MIN_INTERVAL <= 0:
        return
    async with _last_call_lock:
        now = _time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_at = _time.monotonic()
```

Envolver a chamada HTTP em `_get` com o semáforo e o throttle:

```python
    async def _get(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Executa GET request com tratamento de erro e throttle global."""
        try:
            async with _brapi_semaphore:
                await _throttle()
                response = await self._client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
        except httpx.TimeoutException:
            ...  # (manter os except existentes inalterados)
```

> Manter os blocos `except` exatamente como estão hoje (`client.py:161-175`).

- [ ] **Step 4: Run test + suíte**

Run: `.venv/bin/python -m pytest tests/test_brapi_throttle.py -q && .venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/config.py app/repositories/brapi/client.py tests/test_brapi_throttle.py
git commit -m "feat(brapi): throttle global de saida (semaforo compartilhado + intervalo minimo)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Cache quente do universo observado (task no lifespan)

**Files:**
- Create: `app/core/warm_cache.py`
- Modify: `app/config.py` (`warm_cache_enabled`, `warm_cache_interval_sec`, `warm_cache_max_tickers`)
- Modify: `app/main.py` (iniciar/encerrar a task no `lifespan`)
- Test: `tests/test_warm_cache.py`

**Interfaces:**
- Consumes: `is_market_open` (Task 7), `QuoteService`+`LocalQuoteRepository`, `gather_limited`, `WatchlistItemModel`/`AlertModel`/`get_session`
- Produces:
  - `async def watched_universe() -> list[str]`
  - `async def refresh_universe(app: FastAPI) -> int` (retorna nº de tickers processados)
  - `async def warm_cache_loop(app: FastAPI) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_warm_cache.py
"""Testes do cache quente do universo observado."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from app.core import warm_cache
from app.repositories.local.models import (
    AlertModel,
    WatchlistItemModel,
    get_session,
    init_db,
)


@pytest.mark.asyncio
async def test_watched_universe_une_watchlist_e_alertas() -> None:
    await init_db()
    async with get_session() as session:
        session.add(WatchlistItemModel(watchlist_id="w1", ticker="PETR4"))
        session.add(AlertModel(user_id="u1", ticker="vale3", target_price=1, direction="above"))
        await session.commit()
    universo = await warm_cache.watched_universe()
    assert "PETR4" in universo
    assert "VALE3" in universo  # normalizado p/ maiúsculas


@pytest.mark.asyncio
async def test_refresh_respeita_teto_de_tickers(monkeypatch) -> None:
    await init_db()
    async with get_session() as session:
        for i in range(5):
            session.add(WatchlistItemModel(watchlist_id="w1", ticker=f"TICK{i}"))
        await session.commit()

    monkeypatch.setattr(warm_cache.settings, "warm_cache_max_tickers", 3, raising=False)

    app = FastAPI()
    brapi = AsyncMock()
    brapi.quote = AsyncMock(return_value={"results": [{"regularMarketPrice": 10}]})
    app.state.brapi_client = brapi

    processados = await warm_cache.refresh_universe(app)
    assert processados <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_warm_cache.py -q`
Expected: FAIL (`ModuleNotFoundError: app.core.warm_cache`)

- [ ] **Step 3a: Criar `app/core/warm_cache.py`**

```python
"""Cache quente: reaquece, em background, o universo observado.

Universo observado = tickers distintos presentes em watchlists e alertas.
Roda só durante o pregão e respeita um teto de tickers por ciclo para não
estourar a quota do plano free (regra N/T ≤ ~1,7).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import select

from app.config import settings
from app.core.concurrency import gather_limited
from app.core.market_hours import SAO_PAULO, is_market_open
from app.repositories.local.models import (
    AlertModel,
    WatchlistItemModel,
    get_session,
)
from app.repositories.local.quote_repo import LocalQuoteRepository
from app.services.quote_service import QuoteService

logger = logging.getLogger("warm_cache")


async def watched_universe() -> list[str]:
    """Tickers distintos em watchlists ∪ alertas, em maiúsculas."""
    async with get_session() as session:
        wl = await session.execute(select(WatchlistItemModel.ticker).distinct())
        al = await session.execute(select(AlertModel.ticker).distinct())
    tickers = {t.upper() for (t,) in wl.all()} | {t.upper() for (t,) in al.all()}
    return sorted(tickers)


async def refresh_universe(app: FastAPI) -> int:
    """Reaquece o cache de cotação do universo (até o teto). Retorna nº processado."""
    tickers = (await watched_universe())[: settings.warm_cache_max_tickers]
    if not tickers:
        return 0
    service = QuoteService(
        brapi_client=app.state.brapi_client, local_repo=LocalQuoteRepository()
    )
    # get_quote é cache-first: só chama a brapi para os tickers com cache expirado.
    await gather_limited(*(service.get_quote(t) for t in tickers))
    return len(tickers)


async def warm_cache_loop(app: FastAPI) -> None:
    """Loop de background: reaquece o universo no pregão, ocioso fora dele."""
    while True:
        try:
            if is_market_open(datetime.now(SAO_PAULO)):
                n = await refresh_universe(app)
                logger.info("warm cache: %d tickers reaquecidos", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — loop não pode morrer por erro pontual
            logger.exception("warm cache: falha no ciclo")
        await asyncio.sleep(settings.warm_cache_interval_sec)
```

- [ ] **Step 3b: Settings em `app/config.py`**

```python
    # Cache quente (background)
    warm_cache_enabled: bool = True
    warm_cache_interval_sec: int = 900  # 15 min
    warm_cache_max_tickers: int = 25  # N/T ≤ 1,7 com T=15min
```

- [ ] **Step 3c: Iniciar/encerrar no `lifespan` de `app/main.py`**

Atualizar o `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia o ciclo de vida da aplicação."""
    settings.check_production_ready()
    await init_db()
    app.state.brapi_client = BrapiClient()

    warm_task: asyncio.Task[None] | None = None
    if settings.warm_cache_enabled:
        warm_task = asyncio.create_task(warm_cache_loop(app))
        app.state.warm_cache_task = warm_task

    yield

    if warm_task is not None:
        warm_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warm_task
    await app.state.brapi_client.close()
```

Adicionar imports no topo de `app/main.py`:

```python
import asyncio
import contextlib

from app.core.warm_cache import warm_cache_loop
```

> Garantir que `warm_cache_enabled` seja `False` na fixture de testes para a task não competir com a suíte. Em `tests/conftest.py::setup_app`, adicionar `from app.config import settings as _s; _s.warm_cache_enabled = False` antes de instanciar o app (o `lifespan` não roda no `ASGITransport` por padrão, mas deixar explícito evita surpresa se algum teste usar `LifespanManager`).

- [ ] **Step 4: Run test + suíte**

Run: `.venv/bin/python -m pytest tests/test_warm_cache.py -q && .venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Lint/type/suite + Commit**

```bash
.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q
git add app/core/warm_cache.py app/config.py app/main.py tests/test_warm_cache.py tests/conftest.py
git commit -m "feat(cache): cache quente do universo observado via task no lifespan

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Documentação + verificação final

**Files:**
- Create: `docs/06-rate-limit-e-cache.md`
- Test: nenhum novo; rodar a suíte completa e o servidor.

- [ ] **Step 1: Escrever `docs/06-rate-limit-e-cache.md`**

Documento cobrindo: (a) token bucket — namespaces, limites, identidades, resposta 429/Retry-After; (b) cache — camada lazy + tabela genérica, TTLs por tipo, TTL ciente do pregão; (c) cache quente — universo observado, intervalo, teto e a matemática `N/T ≤ 1,7` (15.000/mês); (d) throttle global de saída; (e) limitações conhecidas: estado em memória (reseta no restart, não escala horizontal), `is_market_open` sem feriados B3, identificação por IP via `X-Forwarded-For`. Espelhar o estilo de `docs/05-revisao-seguranca.md`.

- [ ] **Step 2: Verificação verde completa**

Run: `.venv/bin/python -m ruff check app tests && .venv/bin/python -m mypy app && .venv/bin/python -m pytest -q`
Expected: ruff 0, mypy `Success`, todos os testes passando.

- [ ] **Step 3: Smoke test ao vivo (servidor)**

Subir via tool de background (NÃO usar `&`): `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Verificar `/health` (200), `/docs` carrega, e que repetir muito `/auth/login` com credenciais inválidas retorna `429` com header `Retry-After`. Encerrar o servidor ao final.

- [ ] **Step 4: Commit**

```bash
git add docs/06-rate-limit-e-cache.md
git commit -m "docs: rate limiting + cache hardening (06)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de execução

- **Ordem de dependência:** Task 1 → 2 → 3 (rate limit); Task 4 → 5, 6 (cache genérico); Task 7 (pregão) antes/independente; Task 8 (throttle) independente; Task 9 depende de 7. Task 10 por último.
- **Reset do limiter entre testes:** o `limiter` é global; testes de rate limit devem chamar `limiter._buckets.clear()` no início. Já previsto nos testes acima.
- **Estado em memória:** aceitável para single-process/portfólio; Redis seria o upgrade para multi-instância (fora de escopo).
