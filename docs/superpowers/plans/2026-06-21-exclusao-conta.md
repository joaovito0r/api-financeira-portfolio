# Exclusão de Conta (Soft Delete + Janela de Recuperação) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o usuário exclua a própria conta via `DELETE /auth/me`, com uma janela de 30 dias em que a conta fica desativada (sem acesso) mas recuperável automaticamente ao logar de novo; após a janela, um job de background apaga a conta e todos os dados associados permanentemente.

**Architecture:** Soft delete via coluna `users.deleted_at` (nullable). Login com sucesso numa conta em limbo zera `deleted_at` (reativação automática, sem fluxo de email — o projeto não tem infra de envio). Acesso autenticado é bloqueado enquanto `deleted_at` estiver setado. Um loop assíncrono no `lifespan` do FastAPI (mesmo padrão de `warm_cache_loop`) varre periodicamente por contas expiradas e apaga via cascade do ORM.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async (aiosqlite em dev) + Alembic + pytest-asyncio + httpx (testes) + Playwright (verificação manual de frontend).

## Global Constraints

- Tudo async: rotas, sessões de banco, sem chamadas bloqueantes novas.
- `ruff check .` → 0 erros, `mypy app` (strict) → 0 erros, suíte `pytest` 100% verde antes de cada commit.
- Strings visíveis ao usuário (mensagens de erro, UI, toasts) em português.
- Migrations de schema via Alembic (`make migrate-create` / `make migrate`) — nunca alterar tabelas só via `create_all` fora dos testes.
- Seguir o padrão de código já estabelecido: docstrings só quando a razão não é óbvia, sem comentários explicando o que o código já diz, erros de domínio como `ValueError` no service traduzidos para `HTTPException` na rota (padrão usado em todo `app/api/routes/auth.py`).
- Não usar `--no-verify` nem pular hooks de commit.
- Loops de background seguem o padrão de `app/core/warm_cache.py::warm_cache_loop` (try/except `CancelledError: raise` / except genérico só loga, nunca mata o loop).

---

### Task 1: Modelo de dados — `deleted_at`, cascade e migração

**Files:**
- Create: `app/core/time_utils.py`
- Modify: `app/repositories/local/models.py:118-140` (classe `UserModel`)
- Modify: `app/config.py` (novo setting, perto do bloco de `warm_cache_*`, app/config.py:56)
- Create: `alembic/versions/<hash>_add_deleted_at_to_users.py` (via `make migrate-create`)
- Test: `tests/test_account_deletion.py` (novo arquivo)

**Interfaces:**
- Produces: `utcnow_naive() -> datetime.datetime` (em `app/core/time_utils.py`) — usado pelas Tasks 2, 4 e 5.
- Produces: `UserModel.deleted_at: datetime.datetime | None`, `UserModel.alerts`, `UserModel.portfolio_positions` (relações com `cascade="all, delete-orphan"`) — usado pela Task 5.
- Produces: `settings.account_deletion_grace_days: int` (default `30`) — usado pelas Tasks 2 e 5.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_account_deletion.py`:

```python
"""Testes do fluxo de exclusão de conta (soft delete + janela de recuperação)."""

from __future__ import annotations

import uuid

import pytest

from app.repositories.local.models import UserModel, get_session


@pytest.fixture
def unique_email() -> str:
    """Gera email único para cada teste evitar colisão no banco persistido."""
    return f"del_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_user_model_has_deletion_fields() -> None:
    """`deleted_at` existe e é nulo por padrão; relações de cascade existem."""
    async with get_session() as session:
        user = UserModel(
            name="Modelo Teste",
            email=f"modelo_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    assert user.deleted_at is None
    relationship_names = set(UserModel.__mapper__.relationships.keys())
    assert {"alerts", "portfolio_positions", "watchlists"} <= relationship_names
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py -v`
Expected: FAIL — `AttributeError: 'UserModel' object has no attribute 'deleted_at'` (a coluna ainda não existe no modelo).

- [ ] **Step 3: Criar o helper de data/hora**

Criar `app/core/time_utils.py`:

```python
"""Helpers de data/hora compartilhados."""

from __future__ import annotations

import datetime


def utcnow_naive() -> datetime.datetime:
    """Agora em UTC, sem tzinfo.

    As colunas DateTime do projeto guardam datetimes naive; misturar aware e
    naive numa comparação (`>`/`<`) levanta TypeError. Esta função garante
    que todo timestamp da janela de exclusão de conta seja UTC e naive de
    forma consistente, mesmo vindo de arquivos diferentes (auth_service.py,
    account_purge.py).
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
```

- [ ] **Step 4: Adicionar a coluna e as relações em `UserModel`**

Em `app/repositories/local/models.py`, substituir (linhas 132-139):

```python
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now
    )

    # Relacionamentos
    watchlists: Mapped[list[WatchlistModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
```

por:

```python
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Relacionamentos
    watchlists: Mapped[list[WatchlistModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[AlertModel]] = relationship(cascade="all, delete-orphan")
    portfolio_positions: Mapped[list[PortfolioPositionModel]] = relationship(
        cascade="all, delete-orphan"
    )
```

`AlertModel` e `PortfolioPositionModel` são definidos mais abaixo no mesmo arquivo — isso já funciona hoje para `WatchlistModel` (também referenciado antes de ser definido) graças a `from __future__ import annotations` no topo do arquivo; não precisa de import nem de string forward-ref manual.

- [ ] **Step 5: Adicionar o setting da janela de recuperação**

Em `app/config.py`, depois da linha `warm_cache_max_tickers: int = 25  # N/T ≤ 1,7 com T=15min` (linha 56), adicionar:

```python

    # Exclusão de conta (soft delete com janela de recuperação)
    account_deletion_grace_days: int = 30
```

- [ ] **Step 6: Rodar o teste e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py -v`
Expected: PASS

- [ ] **Step 7: Gerar e revisar a migração Alembic**

Run: `make migrate-create m="add deleted_at to users"`

Abrir o arquivo gerado em `alembic/versions/` e confirmar que `upgrade()`/`downgrade()` contêm exatamente isto (revision ids ficam como o Alembic gerou):

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'deleted_at')
```

Se o autogenerate também propuser mudanças não relacionadas (não deveria, já que as novas relações de `alerts`/`portfolio_positions` são só ORM, sem alteração de schema), remova-as do arquivo — só a coluna `deleted_at` deve entrar nesta revisão.

- [ ] **Step 8: Aplicar a migração no banco de dev e confirmar**

```bash
make migrate
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/financeira.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(users)')]
assert 'deleted_at' in cols, cols
print('ok:', cols)
"
```

Expected: imprime a lista de colunas de `users` incluindo `deleted_at`, sem `AssertionError`.

- [ ] **Step 9: Qualidade e suíte completa**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest -q
```

Expected: ruff "All checks passed!", mypy "Success: no issues found", suíte toda verde (nenhuma quebra nos testes existentes).

- [ ] **Step 10: Commit**

```bash
git add app/core/time_utils.py app/repositories/local/models.py app/config.py alembic/versions/ tests/test_account_deletion.py
git commit -m "feat(db): adiciona deleted_at em users + cascade de alerts/portfolio_positions

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Endpoint de exclusão (`DELETE /auth/me`)

**Files:**
- Modify: `app/schemas/auth.py`
- Modify: `app/services/auth_service.py`
- Modify: `app/api/routes/auth.py`
- Test: `tests/test_account_deletion.py`

**Interfaces:**
- Consumes: `UserModel`, `get_session` (`app.repositories.local.models`); `verify_password` (`app.core.security`); `utcnow_naive()` (Task 1, `app.core.time_utils`); `settings.account_deletion_grace_days` (Task 1).
- Produces: `AccountDeletion(BaseModel)` com campo `password: str`; `AuthService.request_deletion(user_id: str, password: str) -> dict[str, Any]` retornando `{"detail": str, "purge_at": str}`; rota `DELETE /auth/me`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_account_deletion.py`:

```python
@pytest.mark.asyncio
async def test_delete_account_wrong_password(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Senha errada não marca a conta para exclusão."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Del Wrong",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_errada"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400

    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == unique_email.lower())
        )
        user = result.scalars().first()
    assert user is not None
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_delete_account_success(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Senha certa marca deleted_at e devolve a data-limite."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Del Ok",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_correta_123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "purge_at" in response.json()

    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == unique_email.lower())
        )
        user = result.scalars().first()
    assert user is not None
    assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_request_deletion_twice_does_not_reset_clock() -> None:
    """Chamar a exclusão de novo numa conta já em limbo não reseta `deleted_at`.

    Testado direto no service (não via HTTP) porque, depois da Task 3, uma
    segunda chamada autenticada nem chegaria no service — o token já seria
    rejeitado em `get_current_user`. Este teste verifica a regra de negócio
    isoladamente, sem depender da ordem das tasks.
    """
    from app.core.security import hash_password
    from app.services.auth_service import AuthService

    async with get_session() as session:
        user = UserModel(
            name="Del Twice Direct",
            email=f"del_twice_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("senha_correta_123"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    service = AuthService()
    await service.request_deletion(user_id, "senha_correta_123")

    with pytest.raises(ValueError, match="já está marcada"):
        await service.request_deletion(user_id, "senha_correta_123")
```

No topo do arquivo, ajustar os imports para incluir o que os novos testes usam:

```python
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.repositories.local.models import UserModel, get_session
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py -v`
Expected: FAIL — `404 Not Found` para `DELETE /auth/me` (rota não existe ainda) e `AttributeError`/`ImportError` para `request_deletion`.

- [ ] **Step 3: Adicionar o schema**

Em `app/schemas/auth.py`, depois da classe `PasswordChange` (linha 44), adicionar:

```python


class AccountDeletion(BaseModel):
    """Schema de exclusão (soft delete) da conta."""

    password: str = Field(..., description="Senha atual, para confirmar a exclusão")
```

- [ ] **Step 4: Implementar `AuthService.request_deletion`**

Em `app/services/auth_service.py`, ajustar os imports do topo (linhas 9-19) de:

```python
from typing import Any

from sqlalchemy import select

from app.core.security import (
    create_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from app.repositories.local.models import UserModel, get_session
```

para:

```python
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.core.security import (
    create_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from app.core.time_utils import utcnow_naive
from app.repositories.local.models import UserModel, get_session
```

E adicionar o método, depois de `update_profile` (depois da linha 161, antes de `change_password`):

```python
    async def request_deletion(self, user_id: str, password: str) -> dict[str, Any]:
        """Marca a conta para exclusão (soft delete), com janela de recuperação.

        Não apaga nenhum dado imediatamente — só registra `deleted_at`. O job
        de background em `app/core/account_purge.py` remove permanentemente
        as contas cuja janela de recuperação já expirou.

        Args:
            user_id: UUID do usuário.
            password: Senha atual em texto puro, para confirmar a operação.

        Returns:
            Dict com mensagem e a data-limite (`purge_at`, ISO 8601) em que a
            conta será apagada permanentemente se o usuário não voltar a logar.

        Raises:
            ValueError: Se o usuário não existir, a senha estiver errada, ou
                a conta já estiver marcada para exclusão.
        """
        async with get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalars().first()
            if not user:
                raise ValueError("Usuário não encontrado")
            if user.deleted_at is not None:
                raise ValueError("Conta já está marcada para exclusão")
            if not verify_password(password, user.password_hash):
                raise ValueError("Senha incorreta")

            user.deleted_at = utcnow_naive()
            await session.commit()

            purge_at = user.deleted_at + timedelta(
                days=settings.account_deletion_grace_days
            )
            return {
                "detail": (
                    "Conta marcada para exclusão. Faça login novamente dentro "
                    "do prazo para reativá-la."
                ),
                "purge_at": purge_at.isoformat(),
            }
```

- [ ] **Step 5: Adicionar a rota**

Em `app/api/routes/auth.py`, ajustar o import de schemas (linhas 14-21) de:

```python
from app.schemas.auth import (
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
```

para:

```python
from app.schemas.auth import (
    AccountDeletion,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
```

E adicionar a rota no final do arquivo:

```python


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
```

- [ ] **Step 6: Rodar e confirmar que passam**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 7: Qualidade e suíte completa**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest -q
```

Expected: tudo verde, sem regressão em `tests/test_auth.py`.

- [ ] **Step 8: Commit**

```bash
git add app/schemas/auth.py app/services/auth_service.py app/api/routes/auth.py tests/test_account_deletion.py
git commit -m "feat(auth): endpoint DELETE /auth/me marca conta para exclusão (soft delete)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Bloqueio de acesso durante o limbo

**Files:**
- Modify: `app/services/auth_service.py` (método `get_current_user`)
- Test: `tests/test_account_deletion.py`

**Interfaces:**
- Consumes: `request_deletion` (Task 2), `get_current_user(token: str) -> dict[str, Any]` (já existente).
- Produces: `get_current_user` agora levanta `ValueError("Conta desativada...")` quando `deleted_at` está setado — consumido pela Task 4 (login precisa continuar funcionando para reativar, então essa checagem só vale para `get_current_user`, não para `login`).

- [ ] **Step 1: Escrever o teste que falha**

Adicionar ao final de `tests/test_account_deletion.py`:

```python
@pytest.mark.asyncio
async def test_token_rejected_after_deletion(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Token emitido antes da exclusão deixa de funcionar em rotas autenticadas."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Bloqueio",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    delete_resp = await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_correta_123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 200

    me = await async_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 401
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py::test_token_rejected_after_deletion -v`
Expected: FAIL — `me.status_code == 200` (a checagem ainda não existe).

- [ ] **Step 3: Implementar a checagem**

Em `app/services/auth_service.py`, no método `get_current_user`, trocar:

```python
            user = result.scalars().first()
            if not user:
                raise ValueError("Usuário não encontrado")

            return {
```

por:

```python
            user = result.scalars().first()
            if not user:
                raise ValueError("Usuário não encontrado")
            if user.deleted_at is not None:
                raise ValueError(
                    "Conta desativada. Faça login novamente para reativá-la."
                )

            return {
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Qualidade e suíte completa**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest -q
```

Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add app/services/auth_service.py tests/test_account_deletion.py
git commit -m "feat(auth): bloqueia acesso de contas marcadas para exclusão

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Reativação automática no login

**Files:**
- Modify: `app/schemas/auth.py` (`TokenResponse`)
- Modify: `app/services/auth_service.py` (método `login`)
- Test: `tests/test_account_deletion.py`

**Interfaces:**
- Consumes: `UserModel.deleted_at` (Task 1).
- Produces: `TokenResponse.reactivated: bool` (default `False`); resposta de `login()` ganha a chave `"reactivated"` — consumido pelo frontend na Task 7.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_account_deletion.py`:

```python
@pytest.mark.asyncio
async def test_login_reactivates_account(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Login com sucesso dentro da janela reativa a conta automaticamente."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Reativa",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    token = reg.json()["access_token"]

    await async_client.request(
        "DELETE",
        "/auth/me",
        json={"password": "senha_correta_123"},
        headers={"Authorization": f"Bearer {token}"},
    )

    login = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_correta_123"},
    )
    assert login.status_code == 200
    data = login.json()
    assert data["reactivated"] is True
    new_token = data["access_token"]

    me = await async_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert me.status_code == 200

    async with get_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == unique_email.lower())
        )
        user = result.scalars().first()
    assert user is not None
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_login_normal_has_no_reactivated_flag(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Login normal (conta nunca excluída) não deve trazer reactivated=True."""
    await async_client.post(
        "/auth/register",
        json={
            "name": "Normal",
            "email": unique_email,
            "password": "senha_correta_123",
        },
    )
    login = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_correta_123"},
    )
    assert login.status_code == 200
    assert login.json()["reactivated"] is False
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py::test_login_reactivates_account tests/test_account_deletion.py::test_login_normal_has_no_reactivated_flag -v`
Expected: FAIL — `KeyError: 'reactivated'` (campo ainda não existe na resposta).

- [ ] **Step 3: Adicionar o campo no schema de resposta**

Em `app/schemas/auth.py`, na classe `TokenResponse`, trocar:

```python
class TokenResponse(BaseModel):
    """Resposta com token JWT."""

    access_token: str = Field(..., description="Token JWT")
    token_type: str = Field("bearer", description="Tipo do token")
    user: UserResponse = Field(..., description="Dados do usuário")
```

por:

```python
class TokenResponse(BaseModel):
    """Resposta com token JWT."""

    access_token: str = Field(..., description="Token JWT")
    token_type: str = Field("bearer", description="Tipo do token")
    user: UserResponse = Field(..., description="Dados do usuário")
    reactivated: bool = Field(
        False,
        description="True se este login reativou uma conta marcada para exclusão",
    )
```

- [ ] **Step 4: Implementar a reativação no `login()`**

Em `app/services/auth_service.py`, no método `login`, trocar:

```python
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
```

por:

```python
            user = result.scalars().first()
            if not user or not verify_password(password, user.password_hash):
                raise ValueError("Email ou senha incorretos")

            reactivated = user.deleted_at is not None
            if reactivated:
                user.deleted_at = None
                await session.commit()

            token = create_access_token(user.id)
            return {
                "access_token": token,
                "token_type": "bearer",
                "reactivated": reactivated,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "created_at": user.created_at.isoformat(),
                },
            }
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `.venv/bin/python -m pytest tests/test_account_deletion.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Qualidade e suíte completa**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest -q
```

Expected: tudo verde, incluindo `tests/test_auth.py::test_login` (que não checava esse campo antes e continua passando porque `reactivated` tem default `False`).

- [ ] **Step 7: Commit**

```bash
git add app/schemas/auth.py app/services/auth_service.py tests/test_account_deletion.py
git commit -m "feat(auth): login reativa automaticamente conta marcada para exclusão

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Purge definitivo (job de background) + wiring no lifespan

**Files:**
- Create: `app/core/account_purge.py`
- Modify: `app/main.py`
- Test: `tests/test_account_purge.py` (novo arquivo)

**Interfaces:**
- Consumes: `UserModel`, `WatchlistModel`, `WatchlistItemModel`, `AlertModel`, `PortfolioPositionModel`, `get_session`, `init_db` (`app.repositories.local.models`); `utcnow_naive()` (Task 1); `settings.account_deletion_grace_days` (Task 1).
- Produces: `purge_expired_accounts() -> int`; `purge_expired_accounts_loop() -> None` (task de background, iniciada no `lifespan`).

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_account_purge.py`:

```python
"""Testes do job de purge definitivo de contas em soft delete."""

from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import select

from app.core import account_purge
from app.core.time_utils import utcnow_naive
from app.repositories.local.models import (
    AlertModel,
    PortfolioPositionModel,
    UserModel,
    WatchlistItemModel,
    WatchlistModel,
    get_session,
    init_db,
)


async def _create_user_with_data(deleted_at: datetime.datetime | None) -> str:
    """Cria um usuário com 1 watchlist+item, 1 alerta e 1 posição. Retorna o id."""
    async with get_session() as session:
        user = UserModel(
            name="Purge Test",
            email=f"purge_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
            deleted_at=deleted_at,
        )
        session.add(user)
        await session.flush()

        watchlist = WatchlistModel(user_id=user.id, name="Principal")
        session.add(watchlist)
        await session.flush()
        session.add(WatchlistItemModel(watchlist_id=watchlist.id, ticker="PETR4"))
        session.add(
            AlertModel(
                user_id=user.id, ticker="VALE3", target_price=10, direction="above"
            )
        )
        session.add(
            PortfolioPositionModel(
                user_id=user.id, ticker="ITUB4", quantity=10, avg_cost=20
            )
        )
        await session.commit()
        return user.id


@pytest.mark.asyncio
async def test_purge_removes_expired_account_and_cascades() -> None:
    await init_db()
    old_enough = utcnow_naive() - datetime.timedelta(days=31)
    user_id = await _create_user_with_data(deleted_at=old_enough)

    removed = await account_purge.purge_expired_accounts()
    assert removed == 1

    async with get_session() as session:
        assert (await session.get(UserModel, user_id)) is None
        watchlists = (
            (
                await session.execute(
                    select(WatchlistModel).where(WatchlistModel.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        alerts = (
            (
                await session.execute(
                    select(AlertModel).where(AlertModel.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        positions = (
            (
                await session.execute(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.user_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert watchlists == []
    assert alerts == []
    assert positions == []


@pytest.mark.asyncio
async def test_purge_keeps_account_within_window() -> None:
    await init_db()
    recent = utcnow_naive() - datetime.timedelta(days=5)
    user_id = await _create_user_with_data(deleted_at=recent)

    removed = await account_purge.purge_expired_accounts()
    assert removed == 0

    async with get_session() as session:
        assert (await session.get(UserModel, user_id)) is not None


@pytest.mark.asyncio
async def test_purge_keeps_active_account() -> None:
    await init_db()
    user_id = await _create_user_with_data(deleted_at=None)

    removed = await account_purge.purge_expired_accounts()
    assert removed == 0

    async with get_session() as session:
        assert (await session.get(UserModel, user_id)) is not None
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv/bin/python -m pytest tests/test_account_purge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.account_purge'`

- [ ] **Step 3: Implementar o módulo de purge**

Criar `app/core/account_purge.py`:

```python
"""Purge definitivo de contas marcadas para exclusão (soft delete) cuja janela
de recuperação expirou.

Mesmo padrão de `app/core/warm_cache.py`: task asyncio de longa duração,
iniciada/encerrada no `lifespan` do FastAPI, sem dependência de cron externo.
"""

from __future__ import annotations

import asyncio
import datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.time_utils import utcnow_naive
from app.repositories.local.models import UserModel, WatchlistModel, get_session

logger = logging.getLogger("account_purge")

_CHECK_INTERVAL_SEC = 3600  # 1h — não é sensível a quota de API externa


async def purge_expired_accounts() -> int:
    """Apaga permanentemente contas cuja janela de recuperação expirou.

    Returns:
        Quantidade de contas removidas neste ciclo.
    """
    cutoff = utcnow_naive() - datetime.timedelta(
        days=settings.account_deletion_grace_days
    )
    async with get_session() as session:
        result = await session.execute(
            select(UserModel)
            .where(UserModel.deleted_at.is_not(None))
            .where(UserModel.deleted_at <= cutoff)
            .options(
                selectinload(UserModel.watchlists).selectinload(
                    WatchlistModel.items
                ),
                selectinload(UserModel.alerts),
                selectinload(UserModel.portfolio_positions),
            )
        )
        expired_users = result.scalars().all()
        for user in expired_users:
            await session.delete(user)
        await session.commit()
        return len(expired_users)


async def purge_expired_accounts_loop() -> None:
    """Loop de background: verifica contas expiradas a cada hora."""
    while True:
        try:
            n = await purge_expired_accounts()
            if n:
                logger.info("purge de contas: %d conta(s) removida(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — loop não pode morrer por erro pontual
            logger.exception("purge de contas: falha no ciclo")
        await asyncio.sleep(_CHECK_INTERVAL_SEC)
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `.venv/bin/python -m pytest tests/test_account_purge.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Ligar o loop no `lifespan` do `main.py`**

Em `app/main.py`, trocar o bloco de imports (linhas 25-28):

```python
from app.config import settings
from app.core.exceptions import RateLimitError
from app.core.migrations import run_migrations
from app.core.warm_cache import warm_cache_loop
from app.repositories.brapi.client import BrapiClient
```

por:

```python
from app.config import settings
from app.core.account_purge import purge_expired_accounts_loop
from app.core.exceptions import RateLimitError
from app.core.migrations import run_migrations
from app.core.warm_cache import warm_cache_loop
from app.repositories.brapi.client import BrapiClient
```

E trocar a função `lifespan` (linhas 38-58):

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia o ciclo de vida da aplicação."""
    # Startup: valida config de produção, aplica migrations e inicia cliente brapi
    settings.check_production_ready()
    await run_migrations()
    app.state.brapi_client = BrapiClient()

    warm_task: asyncio.Task[None] | None = None
    if settings.warm_cache_enabled:
        warm_task = asyncio.create_task(warm_cache_loop(app))
        app.state.warm_cache_task = warm_task

    yield

    # Shutdown: cancela a task de cache quente e fecha conexões
    if warm_task is not None:
        warm_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warm_task
    await app.state.brapi_client.close()
```

por:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia o ciclo de vida da aplicação."""
    # Startup: valida config de produção, aplica migrations e inicia cliente brapi
    settings.check_production_ready()
    await run_migrations()
    app.state.brapi_client = BrapiClient()

    warm_task: asyncio.Task[None] | None = None
    if settings.warm_cache_enabled:
        warm_task = asyncio.create_task(warm_cache_loop(app))
        app.state.warm_cache_task = warm_task

    purge_task = asyncio.create_task(purge_expired_accounts_loop())
    app.state.account_purge_task = purge_task

    yield

    # Shutdown: cancela as tasks de background e fecha conexões
    if warm_task is not None:
        warm_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warm_task
    purge_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await purge_task
    await app.state.brapi_client.close()
```

- [ ] **Step 6: Qualidade e suíte completa**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest -q
```

Expected: tudo verde. A suíte não exercita o `lifespan` real (usa `ASGITransport` sem `LifespanManager`, igual já documentado em `tests/conftest.py` para o warm cache), então a task nova não interfere nos testes.

- [ ] **Step 7: Smoke test manual do startup**

O servidor de dev já costuma estar rodando com `--reload` na porta 8000; ao salvar `app/main.py` ele reinicia automaticamente. Confirmar que subiu sem erro:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected: `{"status":"ok","version":"0.1.0"}`. Se não houver servidor rodando, suba um temporário, confirme o health check e finalize:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 &
sleep 2
curl -s http://127.0.0.1:8123/health
kill %1
```

- [ ] **Step 8: Commit**

```bash
git add app/core/account_purge.py app/main.py tests/test_account_purge.py
git commit -m "feat(auth): job de background apaga permanentemente contas expiradas

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Frontend — Danger Zone, máscara de senha e reativação

**Files:**
- Modify: `app/static/api.js` (`showPrompt`)
- Modify: `app/static/perfil.html`
- Modify: `app/static/login.html` (`doLogin`)

**Interfaces:**
- Consumes: `DELETE /auth/me` (Task 2), resposta de `POST /auth/login` com `reactivated` (Task 4).
- Produces: `showPrompt(title, placeholder = '', defaultValue = '', type = 'text')` — assinatura estendida, 100% compatível com as chamadas existentes (`editarPerfil`, `alterarSenha`, etc., que não passam o 4º argumento).

- [ ] **Step 1: Estender `showPrompt` para suportar máscara de senha**

Em `app/static/api.js`, trocar:

```javascript
function showPrompt(title, placeholder = '', defaultValue = '') {
  _buildModalContainer();
  const titleEl = document.getElementById('hermes-modal-title');
  const msgEl   = document.getElementById('hermes-modal-msg');
  const bodyEl  = document.getElementById('hermes-modal-body');
  const actEl   = document.getElementById('hermes-modal-actions');

  titleEl.innerHTML = title;
  msgEl.innerHTML = '&nbsp;';
  bodyEl.innerHTML = `<input id="hermes-prompt-input" value="${escapeHtml(defaultValue)}" placeholder="${escapeHtml(placeholder)}" autofocus>`;
  actEl.innerHTML = '';
```

por:

```javascript
function showPrompt(title, placeholder = '', defaultValue = '', type = 'text') {
  _buildModalContainer();
  const titleEl = document.getElementById('hermes-modal-title');
  const msgEl   = document.getElementById('hermes-modal-msg');
  const bodyEl  = document.getElementById('hermes-modal-body');
  const actEl   = document.getElementById('hermes-modal-actions');

  titleEl.innerHTML = title;
  msgEl.innerHTML = '&nbsp;';
  bodyEl.innerHTML = `<input id="hermes-prompt-input" type="${escapeHtml(type)}" value="${escapeHtml(defaultValue)}" placeholder="${escapeHtml(placeholder)}" autofocus>`;
  actEl.innerHTML = '';
```

- [ ] **Step 2: Adicionar o botão "Excluir conta" no perfil**

Em `app/static/perfil.html`, trocar:

```html
      <div class="info">
        <div class="info-row danger-zone">
          <span class="l">${icon('logout', { size: 14 })} Sair da conta</span>
          <button class="btn btn-danger btn-sm" onclick="logout()">Sair</button>
        </div>
      </div>`;
```

por:

```html
      <div class="info">
        <div class="info-row danger-zone">
          <span class="l">${icon('logout', { size: 14 })} Sair da conta</span>
          <button class="btn btn-danger btn-sm" onclick="logout()">Sair</button>
        </div>
        <div class="info-row danger-zone">
          <span class="l">${icon('trash', { size: 14 })} Excluir conta</span>
          <button class="btn btn-danger btn-sm" onclick="excluirConta()">Excluir</button>
        </div>
      </div>`;
```

- [ ] **Step 3: Implementar `excluirConta()`**

Em `app/static/perfil.html`, depois da função `logout()` e antes de `document.addEventListener('DOMContentLoaded', carregarPerfil);`, adicionar:

```javascript
async function excluirConta() {
  const ok = await showConfirm(
    'Sua conta será desativada imediatamente. Se você logar novamente dentro de 30 dias, ela é reativada automaticamente — depois desse prazo, a exclusão é permanente e não pode ser desfeita. Quer continuar?',
    'Excluir conta',
    { danger: true }
  );
  if (!ok) return;

  const senha = await showPrompt('Confirme sua senha', 'Senha atual', '', 'password');
  if (!senha) return;

  try {
    const r = await fetch('/auth/me', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ password: senha }),
    });
    const data = await r.json();
    if (!r.ok) { showAlert(data.detail || 'Não foi possível excluir a conta', 'Erro'); return; }

    const prazo = data.purge_at ? new Date(data.purge_at).toLocaleDateString('pt-BR') : null;
    localStorage.removeItem('token');
    showToast(
      prazo
        ? `Conta marcada para exclusão. Logue até ${prazo} para reativá-la.`
        : 'Conta marcada para exclusão.',
      'success',
      6000
    );
    setTimeout(() => { window.location.href = '/static/login.html'; }, 2000);
  } catch (e) {
    showAlert('Erro de conexão: ' + e.message, 'Erro');
  }
}
```

- [ ] **Step 4: Mostrar o toast de reativação no login**

Em `app/static/login.html`, dentro de `doLogin()`, trocar:

```javascript
    const data = await resp.json();
    if (!resp.ok) { showAuthError(data.detail || 'Email ou senha incorretos'); return; }
    localStorage.setItem('token', data.access_token);
    redirectAfterAuth();
```

por:

```javascript
    const data = await resp.json();
    if (!resp.ok) { showAuthError(data.detail || 'Email ou senha incorretos'); return; }
    localStorage.setItem('token', data.access_token);
    if (data.reactivated) {
      showToast('Sua conta foi reativada com sucesso!', 'success');
      setTimeout(redirectAfterAuth, 1200);
      return;
    }
    redirectAfterAuth();
```

- [ ] **Step 5: Verificação manual no navegador (Playwright)**

Servidor já roda com `--reload` na porta 8000, então os arquivos estáticos são servidos atualizados sem reiniciar nada.

5a. Registrar um usuário de teste e guardar o token:

```bash
curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Teste Exclusao","email":"verify_delete_test@example.com","password":"SenhaForte123"}'
```

5b. Escrever e rodar um script Playwright (`/tmp/verify_account_deletion.py`) que: abre `perfil.html` com o token no `localStorage`, clica em "Excluir", confirma o modal de aviso, digita a senha no prompt (verificar `input[type=password]` via `page.locator('#hermes-prompt-input').get_attribute('type')`), confirma, espera o redirect para `login.html`. Depois faz login de novo na UI com as mesmas credenciais e confirma que aparece o toast "Sua conta foi reativada com sucesso!" e que `/auth/me` (via `fetch` no console ou nova chamada) responde 200 com o novo token.

5c. Tirar screenshots (`/tmp/excluir_confirm.png`, `/tmp/excluir_senha.png`, `/tmp/login_reativado.png`) e inspecioná-los para confirmar visualmente o botão, o modal e o toast.

5d. Limpar os dados de teste do banco (mesmo padrão usado nas verificações anteriores desta sessão):

```bash
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/financeira.db')
cur = conn.cursor()
cur.execute(\"DELETE FROM users WHERE email='verify_delete_test@example.com'\")
print('deleted:', cur.rowcount)
conn.commit()
conn.close()
"
rm -f /tmp/verify_account_deletion.py /tmp/excluir_confirm.png /tmp/excluir_senha.png /tmp/login_reativado.png
```

Expected: todos os passos acima funcionam visualmente como descrito; nenhum erro de console JS durante o fluxo.

- [ ] **Step 6: Qualidade e suíte completa**

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest -q
```

Expected: tudo verde (estas mudanças são só frontend, mas confirma que nada no backend quebrou).

- [ ] **Step 7: Commit**

```bash
git add app/static/api.js app/static/perfil.html app/static/login.html
git commit -m "feat(frontend): danger zone com exclusão de conta e reativação no login

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Cobertura do spec:**
- Seção 1 (modelo de dados) → Task 1.
- Seção 2 (`DELETE /auth/me`) → Task 2.
- Seção 3 (bloqueio de acesso) → Task 3.
- Seção 4 (reativação automática) → Task 4.
- Seção 5 (purge em background) → Task 5.
- Seção 6 (frontend) → Task 6.
- Seção 7 (testes) → distribuídos em cada task correspondente (TDD), mais a suíte de purge isolada (Task 5).

**Placeholder scan:** nenhum "TBD"/"implementar depois" — todo step tem código completo. A única coisa deixada para execução é o hash de revisão do Alembic (Task 1, Step 7), que é inerentemente gerado pela ferramenta, não um placeholder de conteúdo.

**Consistência de tipos:** `request_deletion` (Task 2) e `purge_expired_accounts`/`purge_expired_accounts_loop` (Task 5) usam `utcnow_naive()` (Task 1) de forma consistente. `TokenResponse.reactivated` (Task 4) é o mesmo nome de campo lido em `login.html` (`data.reactivated`, Task 6). `AccountDeletion.password` (Task 2) é o mesmo campo enviado por `excluirConta()` (Task 6, `JSON.stringify({ password: senha })`). `showPrompt(..., type)` (Task 6) é chamado com `'password'` exatamente como a nova assinatura espera.
