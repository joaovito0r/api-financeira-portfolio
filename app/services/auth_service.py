"""
Serviço de autenticação de usuários.

Gerencia registro, login, e consulta de perfil.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.security import (
    create_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from app.repositories.local.models import UserModel, get_session


class AuthService:
    """Serviço de autenticação."""

    async def register(self, name: str, email: str, password: str) -> dict[str, Any]:
        """Registra um novo usuário.

        Args:
            name: Nome do usuário.
            email: Email (único).
            password: Senha em texto puro (será hasheada com Argon2).

        Returns:
            Dict com token JWT e dados do usuário.

        Raises:
            ValueError: Se o email já estiver cadastrado.
        """

        async with get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.email == email.lower())
            )
            if result.scalars().first():
                raise ValueError("Email já cadastrado")

            user = UserModel(
                name=name,
                email=email.lower(),
                password_hash=hash_password(password),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            token = create_access_token(user.id)
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "created_at": user.created_at.isoformat(),
                },
            }

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Autentica um usuário.

        Args:
            email: Email do usuário.
            password: Senha em texto puro.

        Returns:
            Dict com token JWT e dados do usuário.

        Raises:
            ValueError: Se email ou senha estiverem incorretos.
        """

        async with get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.email == email.lower())
            )
            user = result.scalars().first()
            if not user or not verify_password(password, user.password_hash):
                raise ValueError("Email ou senha incorretos")

            token = create_access_token(user.id)
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "created_at": user.created_at.isoformat(),
                },
            }

    async def get_current_user(self, token: str) -> dict[str, Any]:
        """Retorna dados do usuário a partir do token JWT.

        Args:
            token: Token JWT.

        Returns:
            Dict com dados do usuário.

        Raises:
            ValueError: Se o token for inválido ou usuário não existir.
        """
        user_id = get_user_id_from_token(token)
        if not user_id:
            raise ValueError("Token inválido ou expirado")

        async with get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalars().first()
            if not user:
                raise ValueError("Usuário não encontrado")

            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            }

    async def update_profile(self, user_id: str, name: str) -> dict[str, Any]:
        """Atualiza o nome do usuário.

        Args:
            user_id: UUID do usuário.
            name: Novo nome.

        Returns:
            Dict com os dados atualizados do usuário.

        Raises:
            ValueError: Se o usuário não existir.
        """
        async with get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalars().first()
            if not user:
                raise ValueError("Usuário não encontrado")

            user.name = name
            await session.commit()
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            }

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        """Troca a senha do usuário, validando a senha atual.

        Args:
            user_id: UUID do usuário.
            current_password: Senha atual em texto puro.
            new_password: Nova senha em texto puro.

        Raises:
            ValueError: Se o usuário não existir ou a senha atual estiver errada.
        """
        async with get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalars().first()
            if not user:
                raise ValueError("Usuário não encontrado")
            if not verify_password(current_password, user.password_hash):
                raise ValueError("Senha atual incorreta")

            user.password_hash = hash_password(new_password)
            await session.commit()
