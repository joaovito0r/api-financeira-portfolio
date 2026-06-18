"""
Dependências da aplicação.

Injeção de dependências para repositórios, serviços e autenticação.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request

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


async def get_current_user(
    authorization: str | None = Header(
        None, description="Token JWT no formato 'Bearer <token>'"
    ),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Extrai e valida o usuário atual a partir do token JWT.

    Pode ser injetada em qualquer rota protegida com `Depends(get_current_user)`.

    Args:
        authorization: Header Authorization.

    Returns:
        Dict com dados do usuário (id, name, email).

    Raises:
        HTTPException 401: Se o token for inválido ou ausente.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail=(
                "Token de acesso não fornecido. Envie no formato 'Bearer <seu_token>'"
            ),
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token ausente ou formato inválido. Use 'Bearer <token>'",
        )

    token = authorization.removeprefix("Bearer ")

    try:
        return await auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
