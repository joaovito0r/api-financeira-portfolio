# 📋 Relatório do Projeto: API Financeira para Portfólio

> Resumo das Etapas 1 a 3 — 31/05/2026

---

## 🗺️ Metodologia: 5 Etapas para Estruturar um Projeto

Este fluxo é **reutilizável** para qualquer projeto futuro.

| Etapa | O quê | Entrega | IA sugerida |
|-------|-------|---------|-------------|
| **1. Domínio & Visão** | Propósito, entidades, regras de negócio, escopo | `docs/01-dominio-e-visao.md` | deepseek-v4-flash |
| **2. Arquitetura** | Camadas, padrões, fluxos, estrutura de diretórios | `docs/02-arquitetura.md` | kimi-k2.6 |
| **3. Tecnologias** | Frameworks, bibliotecas, versões, porquês | `docs/03-tecnologias.md` + `pyproject.toml` | deepseek-v4-pro |
| **4. Implementação** | Código: entidades → schemas → repositórios → serviços → rotas | Código funcional | deepseek-v4-pro |
| **5. Revisão** | Code review, testes, documentação, ajustes finos | PR / versão estável | ds-v4-pro + kimi-k2.6 |

> 📌 **Regra:** A IA sugerida é trocada **somente com permissão do usuário**.

---

## ✅ Etapa 1 — Domínio & Visão

### 🎯 Propósito
API REST que consome [brapi.dev](https://brapi.dev), armazena em banco local com cache inteligente, e expõe dados financeiros estruturados do mercado brasileiro (B3).

### 🧩 9 Entidades do Domínio

```
Ativo (Asset)
  ├── Cotação (Quote)              — snapshot preço em tempo real
  ├── Preço Histórico (OHLCV)      — série temporal abertura/máx/mín/fechamento/volume
  ├── Provento (Dividend)          — dividendos, JCP, bonificações
  ├── Perfil (CompanyProfile)      — dados cadastrais da empresa
  ├── Balanço Patrimonial (BS)     — ativo, passivo, PL
  ├── DRE (IncomeStatement)        — receita, lucro, EBITDA
  ├── Indicadores Financeiros      — ROE, ROA, margens, dívida/PL
  └── Estatísticas-Chave           — P/VP, P/L, EV/EBITDA, beta, DY
```

### 📏 8 Regras de Negócio
1. Identidade única por **ticker** (maiúsculo, sem espaços)
2. Classificação obrigatória: stock, fund, etf, bdr, index
3. Data única por ticker (OHLCV)
4. **Cache-first**: verificar banco antes de chamar brapi.dev
5. Histórico acumulativo (nunca sobrescrever)
6. Rate limit awareness (plano gratuito: 1 ticker/req)
7. Múltiplos proventos por ano por ativo
8. BP e DRE anuais, atrelados ao endDate

### 🔄 Fluxo MVP
```
Cliente → [API REST] → [Cache/Banco] → [brapi.dev]
                ↓
         Resposta JSON
```

---

## ✅ Etapa 2 — Arquitetura

### 🧱 Clean Architecture Leve (4 camadas)

```
┌─────────────────────────────────────────────┐
│              API Layer (FastAPI)             │
│  Routes, validação, serialização             │
├─────────────────────────────────────────────┤
│             Service Layer                    │
│  Casos de uso, regras de negócio, cache      │
├─────────────────────────────────────────────┤
│            Repository Layer                  │
│  Abstração de fontes de dados               │
├─────────────────────────────────────────────┤
│          Data Sources Layer                  │
│     ┌────────────┐   ┌────────────────┐     │
│     │ brapi.dev  │   │ SQLite / PG    │     │
│     │ (externo)  │   │ (local/cache)  │     │
│     └────────────┘   └────────────────┘     │
└─────────────────────────────────────────────┘
```

### 📐 6 Padrões de Design
- **Repository** — abstrai fonte externa da interna
- **Service Layer** — lógica de negócio isolada dos endpoints
- **DTO (Schema)** — Pydantic models nas fronteiras
- **Singleton** — httpx.AsyncClient reutilizado
- **Strategy** — política de cache por tipo de dado
- **DI (FastAPI)** — dependências injetadas

### 🚦 Estratégia de Cache
| Dado | TTL | Justificativa |
|------|-----|---------------|
| Cotação | 15 min | Preço muda em pregão |
| OHLCV | ∞ | Imutável após o pregão |
| Dividendos | ∞ | Proventos passados não mudam |
| Perfil empresa | 24h | Dados cadastrais raros |
| BP / DRE | 7 dias | Balanços são anuais |
| Indicadores | 1h | Mudam com o preço |
| Estatísticas | 1h | Mudam com o mercado |

### 📁 Estrutura Final do Projeto

```
api-financeira-portfolio/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + /health
│   ├── config.py                  # pydantic-settings
│   │
│   ├── api/                       # API Layer
│   │   ├── routes/
│   │   │   ├── quotes.py          # GET /api/quote/{ticker}
│   │   │   ├── assets.py          # GET /api/assets
│   │   │   ├── health.py          # GET /health
│   │   │   └── dividends.py       # GET /api/dividends/{ticker}
│   │   └── deps.py                # DI
│   │
│   ├── domain/                    # Entidades puras
│   ├── schemas/                   # Pydantic DTOs
│   ├── services/                  # Casos de uso
│   ├── repositories/             # Acesso a dados
│   │   ├── base.py                # AbstractRepository[T]
│   │   ├── brapi/                 # brapi.dev HTTP
│   │   └── local/                 # SQLite / SQLAlchemy
│   └── core/                      # Utilitários
│       ├── cache.py
│       ├── http_client.py
│       └── exceptions.py
│
├── tests/                         # Testes
├── docs/                          # Documentação
├── alembic/                       # Migrations
├── pyproject.toml
├── .env.example
├── Makefile
├── .pre-commit-config.yaml
└── README.md
```

### 🔄 Fluxo de Requisição (detalhado)

```
Cliente → GET /api/quote/PETR4
                │
                ▼
        ┌───────────────┐
        │   Route       │  Valida parâmetros
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │   Service     │  1. Verifica cache no banco
        │               │  2. Cache válido → retorna
        │               │  3. Cache expirado → busca fonte
        │               │  4. Salva no banco, retorna
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

---

## ✅ Etapa 3 — Tecnologias

### Stack
| Componente | Escolha | Versão |
|-----------|---------|--------|
| Linguagem | Python | 3.12+ |
| Framework | FastAPI | 0.115+ |
| ORM | SQLAlchemy (async) | 2.0+ |
| Migrations | Alembic | 1.14+ |
| Validação | Pydantic v2 | 2.10+ |
| HTTP | httpx | 0.28+ |
| Config | pydantic-settings | 2.7+ |
| Banco dev | SQLite (aiosqlite) | — |
| Banco prod | PostgreSQL (psycopg) | 16+ |
| Linter/Formatter | ruff | 0.9+ |
| Type checker | mypy (strict) | 1.14+ |
| Testes | pytest + pytest-asyncio | 8.0+ |

### Arquivos gerados
- `pyproject.toml` — dependências + config ruff/mypy/pytest
- `.env.example` — template de variáveis de ambiente
- `.gitignore` — Python + DB + IDE
- `.pre-commit-config.yaml` — ruff + mypy hooks
- `Makefile` — `dev`, `test`, `lint`, `format`, `clean`, `install`
- `app/config.py` — Settings via pydantic-settings
- `app/main.py` — FastAPI app com health check
- `README.md` — visão geral + quick start

---

## ➡️ Próximas Etapas

### Etapa 4 — Implementação (deepseek-v4-pro)
Ordem de criação:
1. **Domain** — classes puras das 9 entidades
2. **Schemas** — Pydantic DTOs (request/response)
3. **Database** — SQLAlchemy models + engine
4. **Repositories** — brapi.client + local repo
5. **Services** — lógica de negócio + cache
6. **Routes** — endpoints FastAPI
7. **Tests** — unitários + integração

### Etapa 5 — Revisão (ds-v4-pro + kimi-k2.6)
- Code review
- Testes complementares
- Documentação OpenAPI
- Ajustes finos

---

## 📌 Links Rápidos

| Recurso | Caminho |
|---------|---------|
| Domínio e Visão | `docs/01-dominio-e-visao.md` |
| Arquitetura | `docs/02-arquitetura.md` |
| Tecnologias | `docs/03-tecnologias.md` |
| Código inicial | `app/main.py` |
| Config | `app/config.py` |
| Deps | `pyproject.toml` |
