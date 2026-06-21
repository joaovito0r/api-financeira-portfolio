"""
Rotas de autenticação.

Endpoints públicos para registro, login e consulta de perfil.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_auth_service, rate_limit_login, rate_limit_user
from app.schemas.auth import (
    AccountDeletion,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Criar conta",
    description="Registra um novo usuário e retorna token JWT.",
    dependencies=[Depends(rate_limit_login)],
)
async def register(
    body: UserCreate,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Registra um novo usuário.

    A senha é hasheada com Argon2 antes de armazenar.
    Retorna um token JWT válido por 7 dias.
    """
    try:
        return await service.register(body.name, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Fazer login",
    description="Autentica com email e senha e retorna token JWT.",
    dependencies=[Depends(rate_limit_login)],
)
async def login(
    body: UserLogin,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Autentica um usuário existente."""
    try:
        return await service.login(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Meus dados",
    description="Retorna os dados do usuário logado.",
)
async def get_me(
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Dados do usuário autenticado."""
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Atualizar perfil",
    description="Atualiza o nome do usuário logado.",
)
async def update_me(
    body: UserUpdate,
    current_user: dict[str, Any] = Depends(rate_limit_user),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Atualiza dados do usuário autenticado."""
    try:
        return await service.update_profile(current_user["id"], body.name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/change-password",
    summary="Trocar senha",
    description="Troca a senha do usuário logado, validando a senha atual.",
)
async def change_password(
    body: PasswordChange,
    current_user: dict[str, Any] = Depends(rate_limit_user),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Troca a senha do usuário autenticado."""
    try:
        await service.change_password(
            current_user["id"], body.current_password, body.new_password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"detail": "Senha alterada com sucesso"}


@router.delete(
    "/me",
    summary="Excluir conta",
    description=(
        "Marca a conta para exclusão (soft delete). A conta fica desativada "
        "por um período de recuperação; logar novamente dentro do prazo a "
        "reativa automaticamente. Depois do prazo, a exclusão é permanente."
    ),
)
async def delete_me(
    body: AccountDeletion,
    current_user: dict[str, Any] = Depends(rate_limit_user),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Solicita a exclusão (soft delete) da conta do usuário autenticado."""
    try:
        return await service.request_deletion(current_user["id"], body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
