"""
Serviço de autenticação de usuários.

Gerencia registro, login, e consulta de perfil.
"""

from __future__ import annotations

from app.core.security import (
    create_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from app.repositories.local.models import UserModel, get_session


class AuthService:
    """Serviço de autenticação."""

    async def register(self, name: str, email: str, password: str) -> dict:
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
        with get_session() as session:
            existing = (
                session.query(UserModel)
                .filter(UserModel.email == email.lower())
                .first()
            )
            if existing:
                raise ValueError("Email já cadastrado")

            user = UserModel(
                name=name,
                email=email.lower(),
                password_hash=hash_password(password),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

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

    async def login(self, email: str, password: str) -> dict:
        """Autentica um usuário.

        Args:
            email: Email do usuário.
            password: Senha em texto puro.

        Returns:
            Dict com token JWT e dados do usuário.

        Raises:
            ValueError: Se email ou senha estiverem incorretos.
        """
        with get_session() as session:
            user = (
                session.query(UserModel)
                .filter(UserModel.email == email.lower())
                .first()
            )
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

    async def get_current_user(self, token: str) -> dict:
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

        with get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                raise ValueError("Usuário não encontrado")

            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            }
