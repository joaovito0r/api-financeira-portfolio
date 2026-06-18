"""
Ponto de entrada da aplicação FastAPI.

Inicializa o app, configura middlewares e registra as rotas.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    alerts,
    assets,
    auth,
    compare,
    dividends,
    fundamental,
    quotes,
    reports,
    watchlists,
)
from app.config import settings
from app.repositories.brapi.client import BrapiClient
from app.repositories.local.models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia o ciclo de vida da aplicação."""
    # Startup: valida config de produção, inicia banco e cliente brapi
    settings.check_production_ready()
    await init_db()
    app.state.brapi_client = BrapiClient()
    yield
    # Shutdown: fecha conexões
    await app.state.brapi_client.close()


app = FastAPI(
    title="API Financeira para Portfólio",
    description="Dados financeiros do mercado brasileiro via brapi.dev",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
)

# ── Registro de Rotas ──────────────────────────────

app.include_router(quotes.router)
app.include_router(dividends.router)
app.include_router(assets.router)
app.include_router(fundamental.router)
app.include_router(auth.router)
app.include_router(watchlists.router)
app.include_router(compare.router)
app.include_router(reports.router)
app.include_router(alerts.router)


# ── Handlers de Erro ──────────────────────────────


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Traduz mensagens de validação do Pydantic para português."""
    erros = []
    for erro in exc.errors():
        # Extrai o nome do campo ignorando estruturas internas (body, query, header)
        loc = [
            str(loc)
            for loc in erro.get("loc", [])
            if loc not in ("body", "query", "header")
        ]
        # Converte índices numéricos para "[posição N]"
        campo_parts: list[str] = []
        for item in loc:
            try:
                int(item)
                campo_parts.append(f"[posição {item}]")
            except ValueError:
                campo_parts.append(item)
        campo = " → ".join(campo_parts) if campo_parts else "geral"

        msg = erro.get("msg", "")
        tipo = erro.get("type", "")

        # Tradução das mensagens comuns
        ctx = erro.get("ctx", {})
        if "string_too_short" in tipo:
            minimo = ctx.get("min_length", "?")
            traduzida = f"{campo}: valor muito curto (mínimo {minimo} caracteres)"
        elif "string_too_long" in tipo:
            maximo = ctx.get("max_length", "?")
            traduzida = f"{campo}: valor muito longo (máximo {maximo} caracteres)"
        elif "missing" in tipo:
            traduzida = f"{campo}: campo obrigatório"
        elif "value_error" in tipo or "literal_error" in tipo:
            traduzida = f"{campo}: valor inválido"
        elif "email" in tipo:
            traduzida = f"{campo}: email inválido"
        else:
            traduzida = f"{campo}: {msg}"

        erros.append({"campo": campo, "mensagem": traduzida})

    return JSONResponse(
        status_code=422,
        content={"detail": erros},
    )


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_model=None)
async def root() -> FileResponse | dict[str, str]:
    """Redireciona para o dashboard."""
    path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"message": "API Financeira - Acesse /docs para documentação"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check da aplicação."""
    return {"status": "ok", "version": "0.1.0"}
