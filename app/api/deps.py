"""
Dependências da aplicação.

Injeção de dependências para repositórios, serviços e autenticação.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from app.repositories.brapi.client import BrapiClient
from app.repositories.local.quote_repo import LocalQuoteRepository
from app.services.auth_service import AuthService
from app.services.quote_service import QuoteService


# ── Serviços ───────────────────────────────────────────

def get_quote_service(request: Request) -> QuoteService:
    """Retorna o serviço de cotações com dependências injetadas."""
    return QuoteService(
        brapi_client=request.app.state.brapi_client,
        local_repo=LocalQuoteRepository(),
    )


# ── Autenticação ───────────────────────────────────────

async def get_current_user(
    authorization: Optional[str] = Header(None, description="Token JWT no formato 'Bearer <token>'"),
) -> dict:
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
            detail="Token de acesso não fornecido. Envie no formato 'Bearer <seu_token>'",
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token ausente ou formato inválido. Use 'Bearer <token>'",
        )

    token = authorization.replace("Bearer ", "")
    auth_service = AuthService()

    try:
        user = await auth_service.get_current_user(token)
        return user
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
