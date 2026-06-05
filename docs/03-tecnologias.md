# Etapa 3: Tecnologias e Dependências

## Stack Principal

| Componente | Escolha | Versão | Motivo |
|-----------|---------|--------|--------|
| **Linguagem** | Python | 3.12+ | Async maduro, tipagem, ecossistema financeiro |
| **Framework web** | FastAPI | 0.115+ | Async nativo, OpenAPI automático, Pydantic integrado |
| **ORM** | SQLAlchemy | 2.0+ (async) | Dialect switcher, migrations, type-safe |
| **Migrations** | Alembic | 1.14+ | Geração automática de migrations |
| **Validação** | Pydantic v2 | 2.10+ | FastAPI usa nativamente, schemas OpenAPI |
| **HTTP Client** | httpx | 0.28+ | Async, connection pooling, TestClient |
| **Config** | pydantic-settings | 2.7+ | Config type-safe via .env |
| **Banco dev** | SQLite (aiosqlite) | — | Zero config, ideal para testes |
| **Banco prod** | PostgreSQL (psycopg) | 16+ | Concorrência, performance |

## Ferramentas de Qualidade

| Ferramenta | Uso |
|-----------|-----|
| **ruff** | Linter + formatter (substitui flake8, isort, black) |
| **mypy** | Static type checking |
| **pytest + pytest-asyncio** | Test runner com suporte async |
| **pre-commit** | Git hooks automáticos |

## Por que não X?

| Rejeitado | Motivo |
|-----------|--------|
| Django REST Framework | Pesado demais pra API proxy com cache |
| Flask | Sem async nativo, sem OpenAPI automático |
| Tortoise-ORM | Menos maduro que SQLAlchemy |
| aiohttp | Ecossistema menor, sem OpenAPI |
| MongoDB | Dados financeiros são relacionais |
| GraphQL | Overkill pra MVP de consulta |

## Dependências

### Produção
- fastapi >= 0.115.0
- uvicorn[standard] >= 0.34.0
- sqlalchemy[asyncio] >= 2.0.36
- alembic >= 1.14.0
- pydantic >= 2.10.0
- pydantic-settings >= 2.7.0
- httpx >= 0.28.0
- aiosqlite >= 0.20.0

### Desenvolvimento
- pytest >= 8.0
- pytest-asyncio >= 0.24.0
- ruff >= 0.9.0
- mypy >= 1.14.0
- pre-commit >= 4.0.0

### Produção (PostgreSQL)
- psycopg[binary] >= 3.2.0
