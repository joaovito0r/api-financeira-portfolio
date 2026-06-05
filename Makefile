.PHONY: dev test lint format clean install

# Desenvolvimento
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Testes
test:
	pytest

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
