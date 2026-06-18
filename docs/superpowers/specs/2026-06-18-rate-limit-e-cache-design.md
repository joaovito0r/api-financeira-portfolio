# Design — Rate limiting (token bucket) + Cache hardening

**Data:** 2026-06-18
**Projeto:** financial_api (FastAPI + SQLAlchemy async + httpx → brapi.dev)
**Status:** Aprovado no brainstorming; pendente revisão final da spec antes do plano.

## Contexto e motivação

A API consome a brapi.dev no **plano gratuito: 15.000 requests/mês** (≈ 714/dia útil ≈
~1,7 req/min durante o pregão). Hoje:

- **Não há rate limiting de entrada** — qualquer cliente autenticado pode martelar os
  endpoints; `core/exceptions.py::RateLimitError` existe mas nunca é levantado (código morto).
- **A limitação de saída é só de concorrência, não global:** `gather_limited` cria um
  semáforo **novo por chamada**, então sob múltiplos usuários a concorrência total contra a
  brapi é efetivamente ilimitada. Não há controle de req/min global.
- **O cache lazy existe e é bom**, mas parcial: `quotes` (15min), `ohlcv` (∞) e `dividends`
  (∞) estão plugados; as políticas de `profile` (24h), `balance` (7d), `indicator`/`statistic`
  (1h) **existem em `core/cache.py` mas não estão ligadas a nenhum repo/tabela** → fundamentos,
  `/compare` e a lista de ativos batem na brapi toda vez.

**Objetivo:** proteger a API (justiça entre usuários) e a quota da brapi, demonstrando design
quota-aware — valor de portfólio.

### Restrição de orçamento (decisão de escopo)

Cachear **todas as ações da B3 proativamente é inviável** no free: 1 ticker/request × ~1.000+
tickers = ~1.000 requests por varredura → ~15 varreduras no mês inteiro. Portanto o cache
quente cobre apenas o **universo observado** (tickers distintos em watchlists + alertas).
Regra de orçamento para `N` tickers atualizados a cada `T` minutos no pregão:
**`N/T ≤ ~1,7`** (ex.: 25 tickers / 15 min, ou 50 / 30 min).

## Decisões tomadas no brainstorming

| Tema | Decisão |
|------|---------|
| Identidade do token bucket | Por `user_id` (autenticado) **+** por IP (rotas públicas) |
| Armazenamento do balde | Em memória, no processo (sem Redis) |
| Perfil de limites | Balanceado |
| Endpoints caros | Balde separado mais restrito |
| TTLs / freshness | Defaults de mercado (sem spike de medição) |
| Cache quente | Task asyncio no `lifespan`, ciente do pregão |

## Seção 1 — Token bucket (entrada)

**Novo módulo `app/core/rate_limit.py`:**

- Classe `TokenBucket(capacity, refill_rate_per_sec)` — algoritmo clássico: tokens repõem
  continuamente até `capacity`; cada request consome 1; sem token → negado. Permite burst até
  `capacity`.
- Registry em memória `dict[str, TokenBucket]` indexado por `namespace:identidade`.
- Limpeza periódica (ou lazy por last-access) de baldes ociosos para não vazar memória.

**Namespaces e limites (perfil balanceado):**

| Balde | Limite sustentado | Burst | Chave |
|-------|-------------------|-------|-------|
| `auth` (autenticado geral) | 60/min (1/s) | 100 | `user_id` |
| `public` (login/registro) | 10/min | 10 | IP |
| `expensive` (`/compare`, `/reports`, multiple quotes) | 10/min | 10 | `user_id` |

**Integração:** dependências FastAPI (`Depends`), no padrão do `deps.py`. A dep de `auth`/
`expensive` roda **depois** do `get_current_user` (lê `user_id`); a de `public` usa o IP de
origem (`request.client.host`, respeitando `X-Forwarded-For` se atrás de proxy — documentar a
limitação). Endpoints caros recebem **as duas** deps (geral + expensive).

**Resposta ao estourar:** `RateLimitError` (agora finalmente usado) → handler retorna
**HTTP 429** com header `Retry-After` (segundos até reabastecer 1 token) e
`X-RateLimit-Limit` / `X-RateLimit-Remaining`. Corpo JSON no padrão de erro existente
(`schemas/error.py`).

**Config:** limites expostos em `config.py` (override via env), com defaults do perfil balanceado.

**Testes:** unidade do `TokenBucket` (refill ao longo do tempo, burst, exhaustão, recuperação);
integração: estourar um endpoint → 429 com `Retry-After`; verificar isolamento entre usuários
(balde de A não afeta B) e entre namespaces.

## Seção 2 — Cache hardening (saída/brapi)

### 2a. Plugar os endpoints órfãos

- **Tabela genérica `cache_entries`** (`key` PK, `payload` JSON, `cached_at`, `policy`) para
  dados lentos: fundamentos (profile/balance/indicator/statistic) e lista de ativos. Evita
  criar 4 tabelas tipadas novas. Quotes/OHLCV/dividendos permanecem nas tabelas tipadas atuais.
- Novo `app/repositories/local/cache_repo.py::GenericCacheRepository` (get/save por chave +
  política), espelhando o padrão de `LocalQuoteRepository`.
- Ligar `fundamental_service`, `asset_service` (lista) e o que `/compare` consome ao cache-first.

### 2b. TTL ciente do pregão

- Helper `app/core/market_hours.py::is_market_open(now)` — seg–sex, 10:00–17:00 BRT
  (America/Sao_Paulo). Feriados B3 ficam **fora de escopo** nesta versão (documentar como
  limitação conhecida).
- `CachePolicy` ganha TTL efetivo ciente do mercado: cotação 15 min no pregão; fora do pregão,
  TTL longo (o preço é estático até a próxima abertura).

### 2c. Cache quente (task no lifespan)

- Novo `app/core/warm_cache.py`: task asyncio iniciada/encerrada no `lifespan`.
- Em intervalo ciente do pregão (ex.: a cada 15 min no pregão; ociosa fora dele), coleta o
  **universo observado** — `SELECT DISTINCT ticker` de `watchlist_items` ∪ `alerts` — e popula
  o cache de cotação via `QuoteService` (respeitando `gather_limited`).
- **Guard de orçamento:** teto configurável de tickers/requests por ciclo respeitando
  `N/T ≤ 1,7`; se o universo exceder, processa o teto e loga warning.
- **Sinergia:** `alert_service.check_all_alerts` passa a ler do cache quente → barato.
- Flag `warm_cache_enabled` (default on; desligável em testes/CI).

**Testes:** `is_market_open` (dentro/fora/fim de semana); warm cache com brapi mockada
(popula cache do universo, respeita o teto, não roda fora do pregão); wiring de cache dos
fundamentos e da lista de ativos (miss→brapi→save; hit→sem brapi).

## Seção 3 — Limite de concorrência/taxa **global** na saída

Corrige o defeito da Seção de contexto:

- Semáforo **único compartilhado** no nível do `BrapiClient` (módulo/instância singleton),
  limitando a concorrência total à brapi independentemente do número de requests concorrentes.
- **Intervalo mínimo entre chamadas** (rate limiter de saída simples — ex.: token bucket de
  saída ou last-call timestamp) para manter req/min dentro do orçamento.
- `gather_limited` continua para o fan-out por request, mas agora sob o teto global.

**Testes:** sob N corrotinas concorrentes, o nº de chamadas simultâneas/min à brapi (mockada)
nunca excede o configurado.

## Seção 4 — Transversal

- **Config** (`config.py`): limites do token bucket, intervalo e teto do warm cache, flags,
  concorrência/intervalo global da brapi.
- **Doc** `docs/06-rate-limit-e-cache.md`: explica o desenho, a matemática do orçamento e as
  limitações conhecidas (feriados, X-Forwarded-For, in-memory não escala horizontal).
- **Qualidade:** manter **ruff 0, mypy strict 0, testes verdes**; novos testes em
  `tests/test_rate_limit.py`, `tests/test_cache.py`, `tests/test_market_hours.py`,
  `tests/test_warm_cache.py`.

## Limitações conhecidas (assumidas nesta versão)

- Estado do rate limit **em memória** → reseta no restart e não escala horizontalmente
  (aceitável para single-process/portfólio; Redis seria o upgrade).
- `is_market_open` **não considera feriados** da B3.
- Identificação por IP depende de `X-Forwarded-For` correto atrás de proxy.

## Fora de escopo

- Cache de **toda** a B3 (inviável no free — ver restrição de orçamento).
- Redis / multi-instância.
- Cache do relatório **montado** (`report_service`) — coberto indiretamente pelos caches
  subjacentes; pode virar follow-up se medição futura mostrar necessidade.
