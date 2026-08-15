"""
Schemas Pydantic para autenticação.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema de registro de usuário."""

    name: str = Field(..., min_length=2, max_length=100, description="Nome do usuário")
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(
        ..., min_length=8, max_length=128, description="Senha (mínimo 8 caracteres)"
    )


class UserLogin(BaseModel):
    """Schema de login."""

    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha")


class UserUpdate(BaseModel):
    """Schema de atualização de perfil."""

    name: str = Field(..., min_length=2, max_length=100, description="Novo nome")


class PasswordChange(BaseModel):
    """Schema de troca de senha."""

    current_password: str = Field(..., description="Senha atual")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Nova senha (mínimo 8 caracteres)",
    )


class AccountDeletion(BaseModel):
    """Schema de exclusão (soft delete) da conta."""

    password: str = Field(..., description="Senha atual, para confirmar a exclusão")


class UserResponse(BaseModel):
    """Resposta com dados do usuário (sem senha)."""

    id: str = Field(..., description="UUID do usuário")
    name: str = Field(..., description="Nome")
    email: str = Field(..., description="Email")
    created_at: datetime = Field(..., description="Data de criação")
    is_demo: bool = Field(
        False,
        description=(
            "True para a conta demo pública; senha e exclusão são bloqueadas "
            "e os dados são restaurados periodicamente"
        ),
    )


class TokenResponse(BaseModel):
    """Resposta com token JWT."""

    access_token: str = Field(..., description="Token JWT")
    token_type: str = Field("bearer", description="Tipo do token")
    user: UserResponse = Field(..., description="Dados do usuário")
    reactivated: bool = Field(
        False,
        description="True se este login reativou uma conta marcada para exclusão",
    )


class ErrorResponse(BaseModel):
    """Resposta padrão para erros."""

    detail: str = Field(..., description="Mensagem de erro")
