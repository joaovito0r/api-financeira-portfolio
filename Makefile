.PHONY: dev test lint format clean install migrate migrate-create migrate-down

# Desenvolvimento
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Testes
test:
	pytest

# Migrations (Alembic) — também rodam automaticamente no startup da app
migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(m)"

migrate-down:
	alembic downgrade -1

# Qualidade
lint:
	ruff check .
	mypy app

format:
	ruff check --fix .
	ruff format .

# Limpeza
clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache
	rm -rf *.egg-info
	rm -rf data/*.db

# Instalação
install:
	pip install -e ".[dev]"

# Pré-commit
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
