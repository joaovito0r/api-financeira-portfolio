# Etapa 2: Arquitetura do Projeto

## 🧱 Visão Geral

Clean Architecture adaptada para um projeto de API financeira de porte médio.
Separação em 4 camadas com responsabilidades bem definidas:

```
┌─────────────────────────────────────────────┐
│              API Layer (FastAPI)             │
│  Routes, validação de input, serialização    │
├─────────────────────────────────────────────┤
│             Service Layer                    │
│  Casos de uso, regras de negócio, cache      │
├─────────────────────────────────────────────┤
│            Repository Layer                  │
│  Abstração de fontes de dados (brapi + DB)  │
├─────────────────────────────────────────────┤
│          Data Sources Layer                  │
│     ┌────────────┐   ┌────────────────┐     │
│     │ brapi.dev  │   │ SQLite/SQLAlch  │     │
│     │ (externo)  │   │ (local/cache)   │     │
│     └────────────┘   └────────────────┘     │
└─────────────────────────────────────────────┘
```

## 📐 Padrões de Design

| Padrão | Onde usar | Motivo |
|--------|-----------|--------|
| **Repository** | Camada de dados | Abstrai fonte externa (brapi) da interna (DB). Troca de provedor = novo repository |
| **Service Layer** | Casos de uso | Lógica de negócio isolada dos endpoints HTTP |
| **DTO (Schema)** | Fronteiras | Pydantic models validam entrada/saída entre camadas |
| **Singleton** | HTTP Client | Um `httpx.AsyncClient` reutilizado (connection pooling) |
| **Strategy** | Cache | Política de cache trocável por tipo de dado (TTL fixo vs. perpétuo) |
| **Dependency Injection** | FastAPI | Substituir repositórios em testes sem tocar no código |

## 🔄 Fluxo de Requisição

```
Cliente → GET /api/quote/PETR4
                │
                ▼
        ┌───────────────┐
        │   Route       │  Valida parâmetros (Pydantic)
        │   Handler     │  Injeta dependências
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │   Service     │  1. Verifica cache no banco local
        │               │  2. Se cache válido → retorna
        │               │  3. Se expirado/ausente → busca na fonte
        │               │  4. Salva no banco, retorna pro cliente
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │  Repository   │  Decide: banco local ou brapi.dev?
        └───────┬───────┘
                │
         ┌──────┴──────┐
         ▼              ▼
     brapi.dev       SQLite
     (HTTP)         (cache)
```

## 🚦 Estratégia de Cache

| Tipo de dado | TTL | Motivo |
|-------------|-----|--------|
| Quote (cotação) | 15 min | Preço muda continuamente em pregão |
| OHLCV (histórico) | ∞ (perpétuo) | Dado imutável após o pregão |
| Dividendos | ∞ (perpétuo) | Proventos passados não mudam |
| CompanyProfile | 24h | Dados cadastrais raramente mudam |
| BalanceSheet / DRE | 7 dias | Balanços são anuais |
| FinancialIndicators | 1h | Indicadores podem mudar com o preço |
| KeyStatistics | 1h | Estatísticas mudam com o mercado |

### Funcionamento do Cache

```
quote_service.get_quote(ticker):
  quote = local_repo.get(ticker)
  if quote and not is_expired(quote, TTL=15min):
      return quote  # cache hit
  data = brapi_repo.fetch_quote(ticker)  # cache miss
  local_repo.save(data)
  return data
```

## 📁 Estrutura de Diretórios

```
api-financeira-portfolio/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, lifespan, startup/shutdown
│   ├── config.py                  # Settings via pydantic-settings
│   │
│   ├── api/                       # API Layer
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── quotes.py          # GET /api/quote/{ticker}
│   │   │   ├── assets.py          # GET /api/assets, /api/available
│   │   │   ├── health.py          # GET /health
│   │   │   └── dividends.py       # GET /api/dividends/{ticker}
│   │   └── deps.py                # FastAPI dependency injection
│   │
│   ├── domain/                    # Domain Layer (entidades puras)
│   │   ├── __init__.py
│   │   ├── asset.py               # Asset entity
│   │   ├── quote.py               # Quote entity
│   │   ├── ohlcv.py               # OHLCV entity
│   │   ├── dividend.py            # Dividend entity
│   │   ├── company_profile.py     # CompanyProfile entity
│   │   ├── balance_sheet.py       # BalanceSheet entity
│   │   ├── income_statement.py    # IncomeStatement entity
│   │   ├── financial_indicator.py # FinancialIndicator entity
│   │   └── key_statistic.py       # KeyStatistic entity
│   │
│   ├── schemas/                   # Pydantic DTOs
│   │   ├── __init__.py
│   │   ├── quote.py               # QuoteRequest, QuoteResponse
│   │   ├── asset.py               # AssetRequest, AssetListResponse
│   │   ├── dividend.py            # DividendResponse
│   │   ├── ohlcv.py               # OHLCVResponse
│   │   ├── company_profile.py     # CompanyProfileResponse
│   │   ├── balance_sheet.py       # BalanceSheetResponse
│   │   ├── income_statement.py    # IncomeStatementResponse
│   │   ├── financial_indicator.py # FinancialIndicatorResponse
│   │   ├── key_statistic.py       # KeyStatisticResponse
│   │   └── error.py               # ErrorResponse
│   │
│   ├── services/                  # Service Layer
│   │   ├── __init__.py
│   │   ├── quote_service.py       # Cotação + cache
│   │   ├── asset_service.py       # Listagem de ativos
│   │   ├── dividend_service.py    # Proventos
│   │   └── historical_service.py  # OHLCV + histórico
│   │
│   ├── repositories/             # Repository Layer
│   │   ├── __init__.py
│   │   ├── base.py               # AbstractRepository[T]
│   │   ├── brapi/                # Implementação brapi.dev
│   │   │   ├── __init__.py
│   │   │   ├── client.py         # Async HTTP client
│   │   │   └── quote_repo.py     # BrapiQuoteRepository
│   │   └── local/                # Implementação SQLite
│   │       ├── __init__.py
│   │       ├── database.py       # Engine + session factory
│   │       ├── models.py         # SQLAlchemy ORM models
│   │       └── quote_repo.py     # LocalQuoteRepository
│   │
│   └── core/                     # Utilitários
│       ├── __init__.py
│       ├── cache.py              # CachePolicy, is_expired
│       ├── http_client.py        # Singleton httpx.AsyncClient
│       └── exceptions.py         # DomainError, NotFoundError, RateLimitError
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Fixtures: test DB, mock client
│   ├── test_quote_service.py
│   ├── test_asset_service.py
│   ├── test_brapi_repo.py
│   ├── test_local_repo.py
│   └── factories/                # Factories para testes
│       ├── __init__.py
│       └── quote_factory.py
│
├── docs/
│   ├── 01-dominio-e-visao.md     ✓
│   └── 02-arquitetura.md         ✓
│
├── alembic/
│   └── ...                       # Migrations (quando necessário)
│
├── .env.example
├── pyproject.toml
├── README.md
└── .gitignore
```

## ⚖️ Trade-offs

| Decisão | Opção escolhida | Alternativa | Motivo |
|---------|----------------|-------------|--------|
| ORM | SQLAlchemy 2.0 (async) | SQLite puro / psycopg raw | Migrations, type safety, troca de dialect |
| HTTP Client | httpx (async) | requests (sync) | Performance, connection pooling, timeouts |
| Validação | Pydantic v2 | attrs / dataclasses | Integração nativa FastAPI, schemas OpenAPI |
| Banco dev | SQLite | PostgreSQL | Zero setup, arquivo único, fácil testar |
| Banco prod | PostgreSQL | SQLite | Concorrência, volume de dados |

## 🧪 Estratégia de Testes

- **Unitários**: Services com repositórios mockados
- **Integração**: Repositórios com SQLite em memória
- **API**: TestClient do FastAPI (httpx)
- **Factories**: Criação rápida de entidades para testes
