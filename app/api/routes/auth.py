"""
Rotas de autenticação.

Endpoints públicos para registro, login e consulta de perfil.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.api.deps import get_current_user
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Criar conta",
    description="Registra um novo usuário e retorna token JWT.",
)
async def register(body: UserCreate) -> dict:
    """Registra um novo usuário.

    A senha é hasheada com Argon2 antes de armazenar.
    Retorna um token JWT válido por 7 dias.
    """
    service = AuthService()
    try:
        return await service.register(body.name, body.email, body.password)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Fazer login",
    description="Autentica com email e senha e retorna token JWT.",
)
async def login(body: UserLogin) -> dict:
    """Autentica um usuário existente."""
    service = AuthService()
    try:
        return await service.login(body.email, body.password)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail=str(e))


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Meus dados",
    description="Retorna os dados do usuário logado.",
)
async def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    """Dados do usuário autenticado."""
    return current_user
