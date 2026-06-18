"""
Módulo de segurança: JWT + Argon2.

Gerencia criação e verificação de tokens JWT e hash de senhas
usando Argon2 (algoritmo vencedor da competição PHC).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# Usa Argon2 como algoritmo de hash de senha
# Argon2 foi o vencedor da Password Hashing Competition (2015)
# É resistente a ataques de GPU e ASIC
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Algoritmo de assinatura do JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    """Gera hash Argon2 da senha.

    Args:
        password: Senha em texto puro.

    Returns:
        Hash da senha no formato Argon2.
    """
    return str(pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica senha contra hash Argon2.

    Args:
        plain_password: Senha em texto puro.
        hashed_password: Hash armazenado.

    Returns:
        True se a senha confere.
    """
    return bool(pwd_context.verify(plain_password, hashed_password))


def create_access_token(user_id: str) -> str:
    """Cria token JWT para um usuário.

    Args:
        user_id: UUID do usuário.

    Returns:
        Token JWT codificado.
    """
    expire = datetime.now(UTC) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return str(jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodifica e valida um token JWT.

    Args:
        token: Token JWT.

    Returns:
        Payload do token ou None se inválido/expirado.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.secret_key, algorithms=[ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> str | None:
    """Extrai o user_id de um token JWT válido.

    Args:
        token: Token JWT.

    Returns:
        UUID do usuário ou None.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    return payload.get("sub")
