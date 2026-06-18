# Rate Limiting + Cache — 2026-06-18

Hardening de consumo: proteção da API contra abuso de entrada (rate limiting) e
proteção da quota do plano free da brapi.dev no consumo de saída (cache + cache
quente + throttle global).

## Resumo

| Mecanismo | Onde | Objetivo |
|-----------|------|----------|
| Token bucket por namespace | `app/core/rate_limit.py` + `app/api/deps.py` | Limitar requisições de entrada por IP/usuário |
| Cache lazy (cache-first) | `app/core/cache.py` + repositórios locais | Evitar reconsultar a brapi dentro do TTL |
| Cache quente (background) | `app/core/warm_cache.py` | Manter o universo observado sempre fresco |
| Throttle global de saída | `app/repositories/brapi/client.py` | Limitar concorrência/ritmo de chamadas à brapi |

## Token bucket (entrada)

Implementação em `app/core/rate_limit.py`: `TokenBucket` é um balde clássico com
reposição contínua (`refill_per_sec`) até a capacidade; cada requisição consome
1 token. `RateLimiter` é um registry de baldes indexados por chave
`"{namespace}:{identidade}"`, mantido em memória (`limiter = RateLimiter()`,
instância global single-process).

A aplicação da política fica em `app/api/deps.py`, via `_enforce(key, capacity,
per_min)`, que só age se `settings.rate_limit_enabled` (padrão `True`). Quatro
namespaces, cada um com sua dependência de rota:

| Namespace | Dependência | Identidade | Capacidade (burst) | Reposição |
|-----------|-------------|------------|---------------------|-----------|
| `login` | `rate_limit_login` | IP | `rate_limit_public_per_min` = 10 | 10/min |
| `data` | `rate_limit_data` | IP | `rate_limit_data_burst` = 100 | `rate_limit_data_per_min` = 60/min |
| `expensive` | `rate_limit_expensive` | IP | `rate_limit_expensive_per_min` = 10 | 10/min |
| `user` | `rate_limit_user` | `user_id` autenticado | `rate_limit_auth_burst` = 100 | `rate_limit_auth_per_min` = 60/min |

Todos os valores vêm de `app/config.py` (`Settings`) e são configuráveis por
variável de ambiente.

**Identidade.** Para os namespaces por IP, `app/api/deps.py::_client_ip` lê
`X-Forwarded-For` (primeiro IP da lista) quando presente; senão usa
`request.client.host`. Para `user`, a dependência `rate_limit_user` substitui
`get_current_user` nas rotas autenticadas — resolve o usuário primeiro e usa
`user["id"]` como identidade, então o limite por usuário sobrevive a troca de
IP/rede.

**Onde cada namespace é aplicado:**
- `login`: `POST /auth/register`, `POST /auth/login` (`app/api/routes/auth.py`)
  — anti brute-force, o mais apertado (10/min, sem burst).
- `data`: rotas públicas leves de leitura — `GET /api/quote/{ticker}`,
  `GET /api/quote/{ticker}/history`, `GET /api/dividends/{ticker}`,
  `GET /api/assets`, `GET /api/available`, e as rotas de fundamentos
  (`/profile`, `/balance-sheet`, `/income-statement`, `/indicators`,
  `/statistics`).
- `expensive`: rotas que fazem fan-out de múltiplas chamadas à brapi por
  requisição — `GET /compare`, `GET /api/quotes` (múltiplos tickers),
  `GET /reports/{ticker}`. Mesmo limite de `login` (10/min) porque cada chamada
  pode custar várias requisições reais à brapi.
- `user`: todas as rotas autenticadas de domínio (`/auth/me`,
  `/me/watchlists/*`, `/me/alerts/*`).

**Resposta 429.** Quando o balde está vazio, `_enforce` lança
`RateLimitError(retry_after, limit)` (`app/core/exceptions.py`). O handler
`rate_limit_handler` em `app/main.py` converte isso em:
- status `429`;
- corpo `{"detail": "Limite de requisições excedido. Tente novamente em instantes."}`;
- header `Retry-After`: segundos até haver saldo (`math.ceil`, mínimo 1; se o
  cálculo for infinito — reposição zero — cai para 60);
- header `X-RateLimit-Limit`: o `per_min` configurado para aquele namespace.

**Estado.** Os baldes vivem em `RateLimiter._buckets`, um dict em memória do
processo. Em testes, o dict é limpo entre casos (`limiter._buckets.clear()`)
para isolar os cenários.

## Cache (saída/brapi)

### Camada lazy cache-first

Não existe um cache "ativo" que decide quando atualizar: a leitura é sempre
cache-first, decidida nos services. Padrão (ex.: `QuoteService.get_quote` em
`app/services/quote_service.py`): tenta o repositório local; se o registro
existir e não estiver expirado, retorna direto; senão chama o `BrapiClient` e
grava o resultado no repositório local antes de retornar. O mesmo padrão se
repete em `FundamentalService` e `AssetService` contra a tabela genérica.

A expiração é decidida por `CachePolicy.is_expired()` em `app/core/cache.py`:
se `perpetual=True`, nunca expira; senão compara `datetime.now() - cached_at`
contra o `effective_ttl()` (que considera o pregão quando `market_aware=True`).

### Duas famílias de armazenamento

**Tabelas tipadas** (`app/repositories/local/models.py`), uma linha por
ticker/registro, com colunas específicas do domínio:
- `QuoteModel` → tabela `quotes` (preço, variação, máxima/mínima do dia,
  volume, abertura, fechamento anterior, market cap, `cached_at`).
- `OHLCVModel` → tabela `ohlcv` (candles históricos por ticker/data).
- `DividendModel` → tabela `dividends` (proventos por ticker/data).

**Tabela genérica** `CacheEntryModel` → tabela `cache_entries`
(`key` como chave primária, `payload` em JSON serializado, `policy` guardando
o TTL usado, `cached_at`), acessada via `GenericCacheRepository.get`/`.save`.
Usada para dados que não têm um esquema tabular dedicado: perfil de empresa,
balanço patrimonial, DRE, indicadores, estatísticas e lista de ativos. Chaves
no padrão `"{tipo}:{TICKER}"` (ex.: `profile:PETR4`, `balance:PETR4`,
`indicators:PETR4`) ou específicas para listagens (`assets:all:{search}:{sector}`,
`assets:available`).

### TTLs por tipo (`app/core/cache.py`)

| Política | TTL no pregão | TTL fora do pregão | Observação |
|----------|---------------|---------------------|------------|
| `QUOTE_CACHE` | 900s (15 min) | 21600s (6h) | `market_aware=True` |
| `OHLCV_CACHE` | perpétuo | perpétuo | candle histórico não muda |
| `DIVIDEND_CACHE` | perpétuo | perpétuo | proventos passados não mudam |
| `PROFILE_CACHE` | 86400s (24h) | — | não é `market_aware` |
| `BALANCE_SHEET_CACHE` | 604800s (7 dias) | — | também usada para DRE |
| `INDICATOR_CACHE` | 3600s (1h) | — | |
| `STATISTIC_CACHE` | 3600s (1h) | — | |
| `ASSET_LIST_CACHE` | 86400s (24h) | — | lista de ativos muda raro |

### TTL ciente do pregão

`is_market_open()` (`app/core/market_hours.py`) define o pregão regular da B3
como **segunda a sexta, 10h–17h horário de Brasília** (`America/Sao_Paulo`,
via `zoneinfo`). Fora desse intervalo (incluindo fins de semana), `QUOTE_CACHE`
usa o TTL estendido de 6h em vez de 15 min — fora do pregão o preço não muda,
então não há motivo para reconsultar a brapi com a mesma frequência.

## Cache quente (background)

`app/core/warm_cache.py` roda uma task asyncio criada no `lifespan` do FastAPI
(`app/main.py`), condicionada a `settings.warm_cache_enabled` (padrão `True`).
A task (`warm_cache_loop`) repete em loop infinito, a cada
`settings.warm_cache_interval_sec` (900s = 15 min):

1. Se `is_market_open()` for falso, não faz nada no ciclo (só dorme e tenta de
   novo no próximo intervalo).
2. Se o pregão estiver aberto, calcula o **universo observado** —
   `watched_universe()`: união de tickers distintos em `WatchlistItemModel` e
   `AlertModel` (watchlists ∪ alertas), em maiúsculas.
3. Corta a lista no teto `settings.warm_cache_max_tickers` (25) e chama
   `QuoteService.get_quote` para cada ticker via `gather_limited` (concorrência
   limitada). Como `get_quote` é cache-first, só gera chamada real à brapi para
   os tickers cujo cache de cotação já expirou — o reaquecimento é incremental,
   não um refresh forçado.

**Por que o teto de 25.** O plano free da brapi.dev permite 15.000
requisições/mês. Distribuído por dias úteis (~21/mês): 15000/21 ≈ 714
req/dia útil. Em minutos de pregão (7h = 420 min): 714/420 ≈ 1,7 req/min de
orçamento sustentável (a regra **N/T ≤ 1,7** citada no código, onde N é o
número de tickers reaquecidos por ciclo e T o intervalo do ciclo em minutos).
Com T = 15 min, N ≤ 1,7 × 15 ≈ 25,5 — daí o teto de 25 tickers por ciclo
(`warm_cache_max_tickers: int = 25  # N/T ≤ 1,7 com T=15min` em
`app/config.py`). Esse orçamento é compartilhado com o tráfego "normal" da
API (cache-first também economiza aqui), então o teto é uma salvaguarda, não o
consumo total esperado.

## Throttle global de saída

Em `app/repositories/brapi/client.py`, todas as chamadas HTTP reais à brapi
passam por dois limitadores compartilhados entre **todas** as instâncias de
`BrapiClient` (variáveis de módulo, não por instância):

- `_brapi_semaphore = asyncio.Semaphore(settings.brapi_max_concurrency)` —
  capa a concorrência simultânea em `brapi_max_concurrency` (padrão **4**).
  Mesmo que vários requests HTTP da API estejam em voo ao mesmo tempo, no
  máximo 4 chamadas reais à brapi acontecem em paralelo.
- `_throttle()` — opcionalmente garante um intervalo mínimo
  (`settings.brapi_min_interval_sec`, padrão `0.0`, ou seja, desligado por
  padrão) entre o fim de uma chamada e o início da próxima, via um lock e
  timestamp compartilhados (`_last_call_lock`, `_last_call_at`).

Os dois mecanismos rodam dentro de `BrapiClient._get`, o ponto único de saída
HTTP do cliente — `async with _brapi_semaphore: await _throttle(); ...` —
então toda rota e a task de cache quente competem pelo mesmo orçamento de
saída.

## Limitações conhecidas

1. **Estado de rate limit em memória.** `RateLimiter._buckets` vive no
   processo Python. Um restart zera todos os baldes (janela de impunidade
   temporária após deploy) e a solução **não escala horizontalmente** — cada
   instância em um setup multi-processo/multi-máquina teria seu próprio
   estado, multiplicando o limite efetivo pelo número de instâncias. Para
   produção com múltiplas instâncias, o upgrade natural é mover o estado do
   bucket para Redis (compartilhado entre instâncias).
2. **`is_market_open()` não considera feriados da B3.** A função olha apenas
   dia da semana (seg–sex) e horário (10h–17h BRT). Em feriados o pregão está
   de fato fechado, mas a função reporta "aberto", então: (a) `QUOTE_CACHE`
   usa o TTL curto (15 min) sem necessidade; (b) o cache quente roda
   normalmente e gasta orçamento da brapi em um dia sem pregão real.
3. **Identificação por IP depende de `X-Forwarded-For` correto.** Os
   namespaces `login`, `data` e `expensive` usam `_client_ip`, que confia no
   primeiro IP do header `X-Forwarded-For` quando presente. Atrás de um proxy
   mal configurado (ou sem proxy, mas com o header forjado pelo próprio
   cliente), isso permite falsificar a identidade usada no rate limit — um
   client malicioso pode enviar um `X-Forwarded-For` diferente em cada
   requisição para evitar o limite. Em produção isso exige um proxy de borda
   confiável que **sobrescreva** (não apenas anexe) o header antes de chegar à
   aplicação.

## Recomendações futuras (não bloqueantes)

1. Mover o estado do token bucket para Redis quando houver mais de uma
   instância da API rodando (escalonamento horizontal).
2. Incorporar um calendário de feriados da B3 em `is_market_open()` (lista
   estática ou API de feriados) para evitar TTL curto e reaquecimento
   desnecessários em dias sem pregão.
3. Validar/restringir `X-Forwarded-For` a uma lista de proxies confiáveis, ou
   usar um cabeçalho assinado pelo proxy de borda, antes de confiar nele para
   rate limiting.
