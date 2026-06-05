# API Financeira para Portfólio

API REST para consulta de dados financeiros do mercado brasileiro (B3),
consumindo dados da [brapi.dev](https://brapi.dev) com cache inteligente
e armazenamento local.

## Funcionalidades

- Cotação em tempo real de ações, FIIs, ETFs, BDRs
- Histórico OHLCV para gráficos de candle
- Dividendos e proventos (DIVIDENDO, JCP, BONIFICAÇÃO)
- Perfil da empresa
- Balanço Patrimonial e DRE
- Indicadores financeiros (ROE, ROA, P/VP, EV/EBITDA, etc.)
- Cache inteligente com TTL por tipo de dado
- Suporte a SQLite (dev) e PostgreSQL (prod)

## Stack

- **Python 3.12+** · **FastAPI** · **SQLAlchemy 2.0 (async)**
- **Pydantic v2** · **httpx** · **Alembic**
- **ruff** · **mypy** · **pytest**

## Quick Start

```bash
# Clone
git clone <repo-url>
cd api-financeira-portfolio

# Ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Dependências
pip install -e ".[dev]"

# Config
cp .env.example .env
# Edite .env com seu token brapi.dev

# Rodar
make dev
# ou: uvicorn app.main:app --reload

# Testes
make test
```

## Documentação

- `/docs` - OpenAPI (automático pelo FastAPI)
- `/docs/01-dominio-e-visao.md` - Domínio e entidades
- `/docs/02-arquitetura.md` - Arquitetura e padrões
- `/docs/03-tecnologias.md` - Stack e dependências

## Licença

MIT
