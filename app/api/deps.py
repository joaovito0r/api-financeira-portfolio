"""
Dependências da aplicação.

Injeção de dependências para repositórios, serviços e autenticação.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.exceptions import RateLimitError
from app.core.rate_limit import limiter
from app.core.validation import normalize_ticker
from app.repositories.local.quote_repo import LocalQuoteRepository
from app.services.auth_service import AuthService
from app.services.quote_service import QuoteService

# ── Validação de entrada ───────────────────────────────


def valid_ticker(ticker: str) -> str:
    """Valida/normaliza um ticker recebido na rota (path ou query).

    Roda antes de qualquer cache ou chamada externa, rejeitando entradas
    malformadas com 422 e impedindo injeção na URL do brapi.
    """
    try:
        return normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


# ── Serviços ───────────────────────────────────────────


def get_quote_service(request: Request) -> QuoteService:
    """Retorna o serviço de cotações com dependências injetadas."""
    return QuoteService(
        brapi_client=request.app.state.brapi_client,
        local_repo=LocalQuoteRepository(),
    )


# ── Autenticação ───────────────────────────────────────


def get_auth_service() -> AuthService:
    """Retorna o serviço de autenticação."""
    return AuthService()


# `auto_error=False`: preferimos o 401 customizado abaixo ao 403 default do
# FastAPI quando o header falta. Declarar como `HTTPBearer` (em vez de ler o
# header "Authorization" manualmente) é o que faz o FastAPI registrar o
# security scheme no OpenAPI — por isso o Swagger mostra o cadeado e o botão
# "Authorize" em toda rota que depende de `get_current_user`.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token JWT obtido em /auth/register ou /auth/login",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Extrai e valida o usuário atual a partir do token JWT.

    Pode ser injetada em qualquer rota protegida com `Depends(get_current_user)`.

    Args:
        credentials: Credenciais Bearer extraídas do header Authorization.

    Returns:
        Dict com dados do usuário (id, name, email).

    Raises:
        HTTPException 401: Se o token for inválido ou ausente.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "Token de acesso não fornecido. Envie no formato 'Bearer <seu_token>'"
            ),
        )

    try:
        return await auth_service.get_current_user(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


# ── Rate limiting ──────────────────────────────────────


def _client_ip(request: Request) -> str:
    """IP de origem, respeitando X-Forwarded-For atrás de proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce(key: str, capacity: int, per_min: int) -> None:
    if not settings.rate_limit_enabled:
        return
    allowed, retry = limiter.check(key, capacity, per_min / 60)
    if not allowed:
        raise RateLimitError(retry_after=retry, limit=per_min)


async def rate_limit_login(request: Request) -> None:
    """Limite estrito por IP para login/registro (anti brute-force)."""
    _enforce(
        f"login:{_client_ip(request)}",
        settings.rate_limit_public_per_min,
        settings.rate_limit_public_per_min,
    )


async def rate_limit_data(request: Request) -> None:
    """Limite geral por IP para rotas públicas de dados leves."""
    _enforce(
        f"data:{_client_ip(request)}",
        settings.rate_limit_data_burst,
        settings.rate_limit_data_per_min,
    )


async def rate_limit_expensive(request: Request) -> None:
    """Limite apertado por IP para endpoints que fazem fan-out na brapi."""
    _enforce(
        f"expensive:{_client_ip(request)}",
        settings.rate_limit_expensive_per_min,
        settings.rate_limit_expensive_per_min,
    )


async def rate_limit_user(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Limite por usuário autenticado; substitui get_current_user nas rotas."""
    _enforce(
        f"user:{user['id']}",
        settings.rate_limit_auth_burst,
        settings.rate_limit_auth_per_min,
    )
    return user
