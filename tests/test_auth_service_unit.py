"""
Testes unitários de AuthService para os caminhos de erro "usuário não
encontrado" — inatingíveis via rota HTTP normal (o token só existe se o
usuário existiu), mas defesa em profundidade caso o usuário seja removido
do banco entre a emissão do token e a chamada (ex.: purge concorrente).
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_get_current_user_nonexistent_id_raises() -> None:
    service = AuthService()
    fake_token = create_access_token(str(uuid.uuid4()))
    with pytest.raises(ValueError, match="não encontrado"):
        await service.get_current_user(fake_token)


@pytest.mark.asyncio
async def test_update_profile_nonexistent_user_raises() -> None:
    service = AuthService()
    with pytest.raises(ValueError, match="não encontrado"):
        await service.update_profile(str(uuid.uuid4()), "Novo Nome")


@pytest.mark.asyncio
async def test_request_deletion_nonexistent_user_raises() -> None:
    service = AuthService()
    with pytest.raises(ValueError, match="não encontrado"):
        await service.request_deletion(str(uuid.uuid4()), "qualquer_senha")


@pytest.mark.asyncio
async def test_change_password_nonexistent_user_raises() -> None:
    service = AuthService()
    with pytest.raises(ValueError, match="não encontrado"):
        await service.change_password(str(uuid.uuid4()), "atual", "nova_senha_123")
