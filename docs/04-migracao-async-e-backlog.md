# Migração Async + Backlog de Correções

> Registro da sessão de **2026-06-16**: migração da camada de banco para
> SQLAlchemy assíncrono e backlog priorizado das próximas correções.

## ✅ O que foi feito nesta sessão

Migração da camada de persistência de **SQLAlchemy síncrono** (embrulhado em
`asyncio.to_thread`) para **SQLAlchemy async real**, ponta a ponta. Os 28 testes
seguem passando.

| Área | Antes | Depois |
|------|-------|--------|
| Engine | `create_engine` (sync) | `create_async_engine` |
| Session | `sessionmaker` | `async_sessionmaker(expire_on_commit=False)` |
| Driver dev | `sqlite+pysqlite` | `sqlite+aiosqlite` |
| Driver prod | `psycopg[binary]` | `asyncpg` |
| Queries | `session.query(...)` (API 1.x) | `select()` + `await session.execute()` + `.scalars()` |
| `init_db()` | sync | `async` (`engine.begin()` + `conn.run_sync(create_all)`) |
| Helper `run_sync` | usado em todos os repos/services | **removido** (desnecessário) |

**Arquivos alterados:**
- `app/config.py` — `database_url` para `sqlite+aiosqlite`
- `pyproject.toml` — `sqlalchemy[asyncio]`, `aiosqlite`, prod `asyncpg`
- `app/repositories/local/models.py` — engine/session/`init_db` async
- `app/repositories/local/{quote,ohlcv,dividend}_repo.py` — `select()` + `async with`
- `app/services/{auth,watchlist,alert}_service.py` — sessões async diretas
- `app/main.py` — `await init_db()` no lifespan
- `tests/conftest.py` — `await init_db()`
- `tests/test_database.py` — adaptado ao padrão async
- `docs/02|03/relatorio` — referências `psycopg` → `asyncpg`

**Detalhes técnicos relevantes:**
- `expire_on_commit=False` para manter atributos acessíveis após o commit (evita
  I/O implícito em objetos detached).
- `watchlist_service` usa `selectinload(WatchlistModel.items)` — em async o
  lazy-load de relacionamento (`len(w.items)`) quebraria com `MissingGreenlet`.
- `AlertModel.triggered == False` → `.is_(False)` (corrige E712 de quebra).
- O README/docs já afirmavam "SQLAlchemy 2.0 (async)"; **agora isso é verdade**.

**Verificação:** 28/28 testes ✓ · `import app.main` ✓ · sem acesso síncrono ao
banco remanescente ✓ · ruff em app/ caiu de 74 → 70 erros (imports mortos removidos).

---

## 🔜 Backlog de correções (próximos passos)

Priorizado. Itens identificados no diagnóstico e **ainda não atacados**.

### 1. Qualidade de tooling (alto impacto p/ portfólio)
- [x] **mypy strict: 176 → 0 erros.** ✅ **CONCLUÍDO (sessão 2026-06-17).**
      `mypy app/` → **Success: no issues found in 54 source files** (com
      `strict = true`). O grosso eram **72 `[type-arg]`** (bare `dict` →
      `dict[str, Any]`, corrigidos só nas linhas apontadas + import de `Any`).
      Os 20 restantes, por categoria: **7 `[assignment]`** (6 = `request:
      Request = None` → `request: Request` reposicionado antes dos params com
      default em `alerts.py`/`compare.py`; 1 = reuso de var `result` em
      `alert_service.check_all_alerts`, renomeado p/ `checked`); **5
      `[no-any-return]`** (`security.py` jose/passlib e `brapi/client.py` →
      `str()`/`bool()`/var tipada); **3 `[no-untyped-def]`** (`main.py` lifespan
      `-> AsyncIterator[None]`, root/health anotados); **2 `[valid-type]` + 2
      `[attr-defined]`** (campo `date` sombreava o tipo `date` em
      `models.py`/`domain/dividend.py` → `import datetime` + `datetime.date`
      qualificado). `ruff format` aplicado nos 11 arquivos tocados.
      ⚠️ Regressão pega pelos testes: anotar `root() -> FileResponse | dict`
      quebrava o FastAPI (response model inválido) → resolvido com
      `@app.get("/", response_model=None)`.
- [x] **ruff: 70 → 0 erros.** ✅ **CONCLUÍDO (sessão 2026-06-17).**
      Adicionado `ignore = ["B008"]` no `pyproject.toml` (falso positivo do
      FastAPI em `Depends`/`Query`/`Header`, 24 ocorrências) com comentário
      explicativo. `ruff check --fix` resolveu 35 (F401, I001, UP017/UP037, etc.).
      Os 20 restantes corrigidos à mão: 15 E501 (quebra de linha em Query/Header,
      f-strings e condições), 3 B904 (`raise ... from e`), 1 ARG001 (`request` →
      `_request` no handler de validação), 1 UP046 (resolvido removendo o arquivo
      órfão — ver item 3). `ruff check app/` → **All checks passed!**

### 2. Correção / robustez

> **Sessão 2026-06-17 — systematic-debugging.** Investigados os 4 itens antes de
> qualquer fix. Conclusão: só 1 era bug de runtime real; os outros 3 são
> higiene/typing ou hardening defensivo (não disparam em fluxo normal).

- [x] **`app/services/report_service.py:93`** — ✅ **CORRIGIDO (bug real).**
      A gambiarra `__import__("datetime").datetime.now()` produzia timestamp
      **naive em hora local**, enquanto o resto da função usa
      `datetime.now(timezone.utc)` (aware). Em UTC−3 o `gerado_em` saía 3h
      defasado e sem offset. Trocado por `datetime.now(timezone.utc).isoformat()`.
      Regressão coberta por `tests/test_report.py::test_gerado_em_e_timezone_aware`.
- [x] **`app/api/routes/alerts.py`** (+ `compare.py`) — ✅ `request: Request = None`
      trocado por `request: Request` (sem default), reposicionado como primeiro
      parâmetro. Resolve o `[assignment]` do mypy e remove a higiene pendente.
- [x] **`app/api/deps.py`** — ✅ trocado `.replace("Bearer ", "")` por
      `.removeprefix("Bearer ")` (sessão 2026-06-17, junto da limpeza ruff).
- [x] **`app/main.py`** — ✅ `erro['ctx']['min_length']`/`['max_length']` agora
      usam `ctx = erro.get("ctx", {})` + `ctx.get(..., "?")` (hardening defensivo
      aplicado na limpeza ruff de 2026-06-17).

### 5. Segurança — ✅ CONCLUÍDO (2026-06-17)
- [x] **`secret_key` default vazio.** Adicionado `@model_validator(mode="after")`
      em `config.py` que gera uma chave aleatória efêmera (`secrets.token_urlsafe(32)`)
      fora de produção, evitando assinar JWT com chave vazia/previsível em dev/test.
- [x] **`check_production_ready` nunca era chamado** (bug latente). Agora roda no
      `lifespan` de `main.py` no startup — em produção falha cedo se `secret_key`
      ou `brapi_token` faltarem.
- [x] Regressão coberta por `tests/test_config.py` (5 testes: gera chave em dev,
      chaves distintas por instância, chave explícita preservada, prod falha sem
      secret, prod ok com config válida).
- [ ] CORS — segue ok enquanto o front é servido na mesma origem via `/static`.

### 3. Limpeza / organização
- [x] **Código morto:** `app/core/http_client.py` (`HTTPClientManager`) ✅
      **REMOVIDO** (2026-06-17). Era um singleton sem nenhum importador; o
      `BrapiClient` cria o próprio `AsyncClient`.
- [x] **Abstração órfã:** `app/repositories/base.py` (`AbstractRepository`) ✅
      **REMOVIDO** (2026-06-17, decisão do João). Não era herdada por ninguém —
      só citada num docstring de `quote_repo.py`, que também foi limpo.
- [x] **DI inconsistente:** ✅ (2026-06-17) criada factory `get_auth_service()`
      em `deps.py`; `routes/auth.py` (register/login) e `get_current_user` agora
      recebem `AuthService` via `Depends(get_auth_service)`. Sem mais
      `AuthService()` solto. (`WatchlistService` segue como singleton de módulo —
      stateless, aceitável.)
- [x] **Imports dentro de função** ✅ movidos para o topo (2026-06-17):
      `routes/auth.py` (`HTTPException` em 2 handlers), `compare.py`
      (`HTTPException`) e `main.py` root (`os` + `FileResponse`).
- [ ] **`typing.Optional/Union`** → sintaxe `X | None` (já tem `from __future__`).
      Obs.: o código já usa majoritariamente `X | None`; varredura final pendente.

### 4. Performance — ✅ CONCLUÍDO (2026-06-17)
- [x] Criado helper `app/core/concurrency.py::gather_limited` (PEP 695 generic),
      que paraleliza com `asyncio.gather` **limitado por `asyncio.Semaphore`**
      (`BRAPI_MAX_CONCURRENCY = 4`, conservador para o plano free → evita 429).
- [x] `generate_report` — as 8 chamadas independentes ao brapi agora rodam em
      paralelo (era o maior gargalo: 8 awaits sequenciais).
- [x] `get_multiple_quotes` e `check_all_alerts` — loops sequenciais trocados por
      `gather_limited`, preservando a ordem dos resultados.
- [x] Testes em `tests/test_concurrency.py` (ordem preservada, limite respeitado,
      lista vazia).
- [x] `compare.py` também fazia chamadas sequenciais por ticker (não estava na
      lista original do item 4). ✅ **CONCLUÍDO (2026-06-18).** As 4 chamadas
      por ticker (cotação, indicadores, estatísticas, perfil) agora rodam em
      paralelo via `gather_limited` para todos os tickers de uma vez.

### 5. Segurança (menor, contexto portfólio)
- [ ] `secret_key` default `""` em dev assina JWT com chave vazia. Gerar default
      aleatória em dev ou falhar cedo.
- [ ] Avaliar CORS (ok enquanto o front é servido na mesma origem via `/static`).
