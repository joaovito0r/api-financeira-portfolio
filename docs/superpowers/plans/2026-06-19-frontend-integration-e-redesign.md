# Frontend: Conectar ao Backend + Redesign Dark/Gold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar todas as páginas do frontend ao backend real (login/registro de verdade, carteira persistida, perfil editável), corrigir os botões/bugs encontrados na auditoria, remover o toggle de tema quebrado, e elevar os gráficos com Chart.js — mantendo o tema dark+dourado já existente.

**Architecture:** Backend FastAPI + SQLAlchemy async já existente (sem mudar arquitetura, só estender com 1 tabela nova + 2 endpoints de auth). Frontend é HTML/JS vanilla servido como estático — sem build step, sem framework. Chart.js entra via CDN (`<script src="https://cdn.jsdelivr.net/npm/chart.js">`), sem bundler.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, Argon2 (passlib), pytest + pytest-asyncio + httpx. Frontend: HTML5, JS vanilla (ES2020+), Chart.js 4.x via CDN.

## Global Constraints

- Toda rota nova segue o padrão multi-tenant existente: filtra por `user_id` extraído de `Depends(rate_limit_user)`.
- Toda função async do backend é `async def` (requisito do projeto — ver `docs/04-migracao-async-e-backlog.md`).
- Rodar ferramentas do venv com `.venv/bin/python -m pytest|ruff|mypy` (shebangs quebrados — nunca `.venv/bin/pytest` direto).
- `ruff check app/ tests/` e `mypy --strict app/` devem ficar em 0 erros ao final de cada task de backend (mesmo padrão que o projeto já mantém).
- Frontend não tem framework de teste JS — verificação é manual (abrir a página no navegador, checar console, clicar no botão). Isso é esperado neste projeto, não é uma lacuna a preencher.
- Toda nova rota autenticada usa `Depends(rate_limit_user)` (não `get_current_user` direto), exatamente como `watchlists.py`/`alerts.py` já fazem.
- Strings voltadas ao usuário (mensagens de erro, labels) em português, igual ao resto do projeto.

---

## Task 1: Modelo `PortfolioPositionModel` + migration

**Files:**
- Modify: `app/repositories/local/models.py`
- Create (via `alembic revision --autogenerate`): `alembic/versions/<hash>_add_portfolio_positions.py`

**Interfaces:**
- Produces: `PortfolioPositionModel` (tabela `portfolio_positions`: `id: str`, `user_id: str`, `ticker: str`, `quantity: int`, `avg_cost: float`, `created_at: datetime`) — usado pela Task 2.

- [ ] **Step 1: Adicionar o modelo em `app/repositories/local/models.py`**

Adicione após a classe `AlertModel` (linha 214, antes de `# ── Engine async ──`):

```python
class PortfolioPositionModel(Base):
    """Tabela de posições da carteira do usuário (ticker/quantidade/custo médio)."""

    __tablename__ = "portfolio_positions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    avg_cost: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )

    # Relacionamentos
    user: Mapped[UserModel] = relationship()
```

- [ ] **Step 2: Gerar a migration**

Run: `cd /home/joao/portifolio/financial_api && .venv/bin/python -m alembic revision --autogenerate -m "add portfolio positions"`

Expected: cria `alembic/versions/<novo_hash>_add_portfolio_positions.py` contendo `op.create_table('portfolio_positions', ...)` com as 5 colunas + FK pra `users.id` com `ondelete='CASCADE'`. Abra o arquivo gerado e confirme que bate com o modelo (mesmo padrão de `ec6072f37840_schema_inicial.py`).

- [ ] **Step 3: Aplicar e verificar a migration**

Run: `.venv/bin/python -m alembic upgrade head`
Expected: `Running upgrade ec6072f37840 -> <novo_hash>, add portfolio positions` sem erro.

Run: `.venv/bin/python -c "import sqlite3; c=sqlite3.connect('financeiro.db' if __import__('os').path.exists('financeiro.db') else [f for f in __import__('os').listdir('.') if f.endswith('.db')][0]); print(c.execute(\"select name from sqlite_master where type='table'\").fetchall())"`
Expected: lista de tabelas inclui `portfolio_positions`.

- [ ] **Step 4: Commit**

```bash
git add app/repositories/local/models.py alembic/versions/
git commit -m "feat(db): adiciona tabela portfolio_positions"
```

---

## Task 2: `PortfolioService` (TDD)

**Files:**
- Create: `app/services/portfolio_service.py`
- Test: `tests/test_portfolio_service.py`

**Interfaces:**
- Consumes: `PortfolioPositionModel`, `get_session` de `app.repositories.local.models` (Task 1).
- Produces: classe `PortfolioService` com métodos `list_positions(user_id) -> list[dict]`, `add_position(user_id, ticker, quantity, avg_cost) -> dict`, `update_position(user_id, position_id, quantity=None, avg_cost=None) -> dict | None`, `delete_position(user_id, position_id) -> bool`. Cada dict tem chaves `id, ticker, quantity, avg_cost, created_at`. Usado pela Task 3.

- [ ] **Step 1: Escrever o teste (vai falhar — módulo não existe)**

Crie `tests/test_portfolio_service.py`:

```python
"""
Testes do serviço de carteira (posições).
"""

from __future__ import annotations

import uuid

import pytest

from app.repositories.local.models import UserModel, get_session
from app.services.portfolio_service import PortfolioService


@pytest.fixture
async def user_id() -> str:
    """Cria um usuário direto no banco e retorna o id."""
    async with get_session() as session:
        user = UserModel(
            name="Portfolio Service User",
            email=f"psvc_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


@pytest.mark.asyncio
async def test_add_and_list_position(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "PETR4", 100, 38.5)
    assert created["ticker"] == "PETR4"
    assert created["quantity"] == 100
    assert created["avg_cost"] == 38.5

    positions = await service.list_positions(user_id)
    tickers = [p["ticker"] for p in positions]
    assert "PETR4" in tickers


@pytest.mark.asyncio
async def test_list_positions_isolated_by_user(user_id: str) -> None:
    other_id = str(uuid.uuid4())
    service = PortfolioService()
    await service.add_position(user_id, "VALE3", 50, 60.0)
    other_positions = await service.list_positions(other_id)
    assert other_positions == []


@pytest.mark.asyncio
async def test_update_position(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "ITUB4", 10, 30.0)
    updated = await service.update_position(
        user_id, created["id"], quantity=20, avg_cost=32.0
    )
    assert updated is not None
    assert updated["quantity"] == 20
    assert updated["avg_cost"] == 32.0


@pytest.mark.asyncio
async def test_update_position_wrong_user_returns_none(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "BBAS3", 10, 20.0)
    result = await service.update_position(
        str(uuid.uuid4()), created["id"], quantity=99
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_position(user_id: str) -> None:
    service = PortfolioService()
    created = await service.add_position(user_id, "WEGE3", 5, 40.0)
    deleted = await service.delete_position(user_id, created["id"])
    assert deleted is True

    positions = await service.list_positions(user_id)
    ids = [p["id"] for p in positions]
    assert created["id"] not in ids


@pytest.mark.asyncio
async def test_delete_position_not_found(user_id: str) -> None:
    service = PortfolioService()
    deleted = await service.delete_position(user_id, str(uuid.uuid4()))
    assert deleted is False
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_portfolio_service.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.portfolio_service'`

- [ ] **Step 3: Implementar `app/services/portfolio_service.py`**

```python
"""
Serviço de carteira (posições de ativos do usuário).

Gerencia ticker/quantidade/custo médio por usuário.
Multi-tenancy: toda operação filtra por user_id.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.repositories.local.models import PortfolioPositionModel, get_session


class PortfolioService:
    """Serviço de gerenciamento da carteira de ativos."""

    async def list_positions(self, user_id: str) -> list[dict[str, Any]]:
        """Lista todas as posições da carteira do usuário."""
        async with get_session() as session:
            result = await session.execute(
                select(PortfolioPositionModel).where(
                    PortfolioPositionModel.user_id == user_id
                )
            )
            positions = result.scalars().all()
            return [self._to_dict(p) for p in positions]

    async def add_position(
        self, user_id: str, ticker: str, quantity: int, avg_cost: float
    ) -> dict[str, Any]:
        """Adiciona uma posição à carteira."""
        async with get_session() as session:
            position = PortfolioPositionModel(
                user_id=user_id,
                ticker=ticker.upper(),
                quantity=quantity,
                avg_cost=avg_cost,
            )
            session.add(position)
            await session.commit()
            await session.refresh(position)
            return self._to_dict(position)

    async def update_position(
        self,
        user_id: str,
        position_id: str,
        quantity: int | None = None,
        avg_cost: float | None = None,
    ) -> dict[str, Any] | None:
        """Atualiza quantidade e/ou custo médio de uma posição."""
        async with get_session() as session:
            result = await session.execute(
                select(PortfolioPositionModel).where(
                    PortfolioPositionModel.id == position_id,
                    PortfolioPositionModel.user_id == user_id,
                )
            )
            position = result.scalars().first()
            if not position:
                return None

            if quantity is not None:
                position.quantity = quantity
            if avg_cost is not None:
                position.avg_cost = avg_cost

            await session.commit()
            return self._to_dict(position)

    async def delete_position(self, user_id: str, position_id: str) -> bool:
        """Remove uma posição da carteira."""
        async with get_session() as session:
            result = await session.execute(
                select(PortfolioPositionModel).where(
                    PortfolioPositionModel.id == position_id,
                    PortfolioPositionModel.user_id == user_id,
                )
            )
            position = result.scalars().first()
            if not position:
                return False

            await session.delete(position)
            await session.commit()
            return True

    @staticmethod
    def _to_dict(position: PortfolioPositionModel) -> dict[str, Any]:
        return {
            "id": position.id,
            "ticker": position.ticker,
            "quantity": position.quantity,
            "avg_cost": position.avg_cost,
            "created_at": position.created_at.isoformat(),
        }
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_portfolio_service.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/portfolio_service.py tests/test_portfolio_service.py
git commit -m "feat(portfolio): adiciona PortfolioService com testes"
```

---

## Task 3: Rotas `/me/portfolio`

**Files:**
- Create: `app/api/routes/portfolio.py`
- Modify: `app/main.py` (registrar router)
- Test: `tests/test_portfolio.py`

**Interfaces:**
- Consumes: `PortfolioService` (Task 2), `rate_limit_user` de `app.api.deps`, `normalize_ticker` de `app.core.validation`.
- Produces: `GET /me/portfolio`, `POST /me/portfolio`, `PATCH /me/portfolio/{position_id}`, `DELETE /me/portfolio/{position_id}` — usados pela Task 11 (frontend).

- [ ] **Step 1: Escrever o teste (vai falhar — rota não existe, 404)**

Crie `tests/test_portfolio.py` (mesmo padrão de `tests/test_watchlists.py`):

```python
"""
Testes das rotas de carteira (portfolio).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth_token(async_client: AsyncClient) -> str:
    """Registra e retorna token de autenticação (email único por chamada)."""
    suffix = uuid.uuid4().hex[:8]
    response = await async_client.post(
        "/auth/register",
        json={
            "name": "Portfolio User",
            "email": f"pf_user_{suffix}@example.com",
            "password": "senha_segura_123",
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_add_position(async_client: AsyncClient, auth_token: str) -> None:
    response = await async_client.post(
        "/me/portfolio?ticker=PETR4&quantity=100&avg_cost=38.5",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "PETR4"
    assert data["quantity"] == 100
    assert data["avg_cost"] == 38.5
    assert "id" in data


@pytest.mark.asyncio
async def test_list_positions(async_client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    await async_client.post(
        "/me/portfolio?ticker=VALE3&quantity=50&avg_cost=60", headers=headers
    )
    await async_client.post(
        "/me/portfolio?ticker=ITUB4&quantity=80&avg_cost=30", headers=headers
    )
    response = await async_client.get("/me/portfolio", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    tickers = [p["ticker"] for p in data["positions"]]
    assert "VALE3" in tickers
    assert "ITUB4" in tickers


@pytest.mark.asyncio
async def test_update_position(async_client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    created = await async_client.post(
        "/me/portfolio?ticker=BBAS3&quantity=10&avg_cost=20", headers=headers
    )
    pos_id = created.json()["id"]
    response = await async_client.patch(
        f"/me/portfolio/{pos_id}?quantity=15&avg_cost=22", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 15
    assert data["avg_cost"] == 22


@pytest.mark.asyncio
async def test_delete_position(async_client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    created = await async_client.post(
        "/me/portfolio?ticker=WEGE3&quantity=5&avg_cost=40", headers=headers
    )
    pos_id = created.json()["id"]
    response = await async_client.delete(f"/me/portfolio/{pos_id}", headers=headers)
    assert response.status_code == 200

    list_resp = await async_client.get("/me/portfolio", headers=headers)
    ids = [p["id"] for p in list_resp.json()["positions"]]
    assert pos_id not in ids


@pytest.mark.asyncio
async def test_delete_position_not_found(
    async_client: AsyncClient, auth_token: str
) -> None:
    response = await async_client.delete(
        f"/me/portfolio/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_unauthorized(async_client: AsyncClient) -> None:
    response = await async_client.get("/me/portfolio")
    assert response.status_code == 401
    response = await async_client.post(
        "/me/portfolio?ticker=PETR4&quantity=1&avg_cost=1"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_add_position_invalid_ticker(
    async_client: AsyncClient, auth_token: str
) -> None:
    response = await async_client.post(
        "/me/portfolio?ticker=***&quantity=1&avg_cost=1",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_portfolio.py -v`
Expected: `404 Not Found` em todos os testes (rota não registrada ainda).

- [ ] **Step 3: Implementar `app/api/routes/portfolio.py`**

```python
"""
Rotas de carteira (posições de ativos do usuário).

Todas as rotas exigem autenticação JWT.
O usuário só acessa suas próprias posições (multi-tenancy).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import rate_limit_user
from app.core.validation import normalize_ticker
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/me/portfolio", tags=["Carteira"])
service = PortfolioService()


@router.get("", summary="Listar posições da carteira")
async def list_positions(
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Lista todas as posições da carteira do usuário logado."""
    positions = await service.list_positions(current_user["id"])
    return {"positions": positions, "total": len(positions)}


@router.post("", summary="Adicionar posição")
async def add_position(
    ticker: str = Query(..., description="Ticker do ativo (ex: PETR4)"),
    quantity: int = Query(..., gt=0, description="Quantidade de ações"),
    avg_cost: float = Query(..., gt=0, description="Preço médio de compra"),
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Adiciona um ativo à carteira."""
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return await service.add_position(current_user["id"], ticker, quantity, avg_cost)


@router.patch("/{position_id}", summary="Atualizar posição")
async def update_position(
    position_id: str,
    quantity: int | None = Query(None, gt=0),
    avg_cost: float | None = Query(None, gt=0),
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Atualiza quantidade e/ou custo médio de uma posição."""
    result = await service.update_position(
        current_user["id"], position_id, quantity=quantity, avg_cost=avg_cost
    )
    if not result:
        raise HTTPException(status_code=404, detail="Posição não encontrada")
    return result


@router.delete("/{position_id}", summary="Remover posição")
async def delete_position(
    position_id: str,
    current_user: dict[str, Any] = Depends(rate_limit_user),
) -> dict[str, Any]:
    """Remove uma posição da carteira."""
    deleted = await service.delete_position(current_user["id"], position_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Posição não encontrada")
    return {"detail": "Posição removida com sucesso"}
```

- [ ] **Step 4: Registrar o router em `app/main.py`**

No bloco de imports (linha 21-31), adicione `portfolio` à lista (ordem alfabética, entre `fundamental` e `quotes`):

```python
from app.api.routes import (
    alerts,
    assets,
    auth,
    compare,
    dividends,
    fundamental,
    portfolio,
    quotes,
    reports,
    watchlists,
)
```

Na seção `# ── Registro de Rotas ──` (linha 72-80), adicione:

```python
app.include_router(portfolio.router)
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_portfolio.py -v`
Expected: `7 passed`

Run: `.venv/bin/python -m pytest -q` (suíte completa)
Expected: todos os testes passam, nenhuma regressão.

Run: `.venv/bin/python -m ruff check app/ tests/`
Expected: `All checks passed!`

Run: `.venv/bin/python -m mypy --strict app/`
Expected: `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
git add app/api/routes/portfolio.py app/main.py tests/test_portfolio.py
git commit -m "feat(portfolio): adiciona rotas /me/portfolio"
```

---

## Task 4: `PATCH /auth/me` (editar nome) + `POST /auth/change-password`

**Files:**
- Modify: `app/schemas/auth.py` (novos schemas)
- Modify: `app/services/auth_service.py` (novos métodos)
- Modify: `app/api/routes/auth.py` (novas rotas)
- Modify: `tests/test_auth.py` (novos testes)

**Interfaces:**
- Produces: `PATCH /auth/me` (body `UserUpdate{name}`) → `UserResponse`; `POST /auth/change-password` (body `PasswordChange{current_password, new_password}`) → `{"detail": str}`. Usados pela Task 10 (frontend `perfil.html`).

- [ ] **Step 1: Escrever os testes (vão falhar — 404/405)**

Adicione ao final de `tests/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_update_profile(async_client: AsyncClient, unique_email: str) -> None:
    """Verifica atualização do nome do usuário."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Nome Antigo",
            "email": unique_email,
            "password": "senha_segura_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.patch(
        "/auth/me",
        json={"name": "Nome Novo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nome Novo"

    me = await async_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.json()["name"] == "Nome Novo"


@pytest.mark.asyncio
async def test_update_profile_unauthorized(async_client: AsyncClient) -> None:
    response = await async_client.patch("/auth/me", json={"name": "X"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password(async_client: AsyncClient, unique_email: str) -> None:
    """Verifica troca de senha e que a nova senha passa a funcionar no login."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Troca Senha",
            "email": unique_email,
            "password": "senha_antiga_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.post(
        "/auth/change-password",
        json={
            "current_password": "senha_antiga_123",
            "new_password": "senha_nova_456",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    login = await async_client.post(
        "/auth/login",
        json={"email": unique_email, "password": "senha_nova_456"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    async_client: AsyncClient, unique_email: str
) -> None:
    """Verifica que senha atual incorreta é rejeitada."""
    reg = await async_client.post(
        "/auth/register",
        json={
            "name": "Senha Errada",
            "email": unique_email,
            "password": "senha_certa_123",
        },
    )
    token = reg.json()["access_token"]

    response = await async_client.post(
        "/auth/change-password",
        json={"current_password": "senha_errada", "new_password": "nova_senha_999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_auth.py -k "update_profile or change_password" -v`
Expected: `404 Not Found` (rotas não existem).

- [ ] **Step 3: Adicionar schemas em `app/schemas/auth.py`**

Adicione após `UserLogin`:

```python
class UserUpdate(BaseModel):
    """Schema de atualização de perfil."""

    name: str = Field(..., min_length=2, max_length=100, description="Novo nome")


class PasswordChange(BaseModel):
    """Schema de troca de senha."""

    current_password: str = Field(..., description="Senha atual")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="Nova senha (mínimo 8 caracteres)"
    )
```

- [ ] **Step 4: Adicionar métodos em `app/services/auth_service.py`**

Adicione ao final da classe `AuthService` (depois de `get_current_user`):

```python
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
```

- [ ] **Step 5: Adicionar rotas em `app/api/routes/auth.py`**

Atualize o import (linha 14):

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

Adicione ao final do arquivo, depois de `get_me`:

```python
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
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: todos os testes passam (os antigos + os 4 novos).

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check app/ tests/ && .venv/bin/python -m mypy --strict app/`
Expected: suíte completa passa, ruff e mypy zerados.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/auth.py app/services/auth_service.py app/api/routes/auth.py tests/test_auth.py
git commit -m "feat(auth): adiciona PATCH /auth/me e POST /auth/change-password"
```

---

## Task 5: Helpers de auth no `api.js` + remover toggle de tema

**Files:**
- Modify: `app/static/api.js`
- Modify: `app/static/dashboard.html`

**Interfaces:**
- Produces: `getToken()`, `requireAuth()`, `authHeaders()` em `api.js` — usados pelas Tasks 7-10 (login.html, watchlists.html, alertas.html, perfil.html, carteira.html).
- Removes: `currentTheme()`, `applyTheme()`, `toggleTheme()` de `api.js`; botão `#theme-toggle` e script de FOUC de `dashboard.html`.

Não há teste automatizado de JS neste projeto (sem framework de teste front-end) — verificação é manual: abrir a página, abrir o console do navegador, confirmar zero erros.

- [ ] **Step 1: Remover o bloco de tema do `api.js`**

Em `app/static/api.js`, remova inteiramente este bloco (linhas ~308-333):

```js
// ── Theme toggle (light/dark) ──────────────────────────────────────────────

function currentTheme() {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

function applyTheme(theme) {
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  try { localStorage.setItem('financeiro_theme', theme); } catch(e) {}
  // Atualiza o ícone do botão (se existir)
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.innerHTML = theme === 'light'
      ? icon('refresh', { size: 14 }) // placeholder, vai ser re-hidratado
      : icon('refresh', { size: 14 });
    hydrateIcons(btn);
  }
}

function toggleTheme() {
  applyTheme(currentTheme() === 'light' ? 'dark' : 'light');
}
```

No lugar dele, adicione:

```js
// ── Autenticação ─────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('token');
}

/**
 * Garante que existe um token; se não houver, redireciona para o login
 * preservando a página atual em ?redirect= para voltar depois.
 * @returns {string|null} o token, ou null (e já disparou o redirect)
 */
function requireAuth() {
  const token = getToken();
  if (!token) {
    const redirect = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/static/login.html?redirect=${redirect}`;
    return null;
  }
  return token;
}

function authHeaders() {
  return { 'Authorization': `Bearer ${getToken()}` };
}
```

- [ ] **Step 2: Remover o botão e o script de tema de `dashboard.html`**

Remova o script de FOUC no `<head>` (linhas 15-23):

```html
  <script>
    // Aplica tema persistido antes da renderização (evita flash)
    (function() {
      try {
        const t = localStorage.getItem('financeiro_theme');
        if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
      } catch(e) {}
    })();
  </script>
```

Remova o botão de toggle na sidebar (linhas 56-60):

```html
  <div style="display:flex;gap:4px;padding:0 10px;margin-bottom:8px;">
    <button class="theme-toggle" id="theme-toggle" aria-label="Alternar tema" title="Alternar tema">
      <span data-icon="refresh" data-icon-size="14"></span>
    </button>
  </div>
```

Remova a linha que registra o listener do toggle dentro do `DOMContentLoaded` (perto do final do script):

```js
  // Tema toggle
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
```

- [ ] **Step 3: Verificar manualmente**

Run: `.venv/bin/python -m uvicorn app.main:app --port 8000` (background) e abra `http://127.0.0.1:8000/` no navegador.
Expected: sidebar não tem mais o botão de alternar tema; console sem erros `toggleTheme is not defined` ou similares.

- [ ] **Step 4: Commit**

```bash
git add app/static/api.js app/static/dashboard.html
git commit -m "refactor(frontend): remove toggle de tema quebrado, adiciona helpers de auth"
```

---

## Task 6: Página `login.html` (login + registro reais)

**Files:**
- Create: `app/static/login.html`

**Interfaces:**
- Consumes: `POST /auth/login`, `POST /auth/register` (já existentes), `escapeHtml`/`showAlert` de `api.js`.
- Produces: ao logar com sucesso, grava `localStorage.setItem('token', ...)` e redireciona para `?redirect=` (ou `/` por padrão). Usado pelas Tasks 7-10, que redirecionam pra aqui via `requireAuth()`.

Sem teste automatizado (página estática) — verificação manual no Step 3.

- [ ] **Step 1: Criar `app/static/login.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>API Financeira — Entrar</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='12' cy='12' r='10' fill='%23d6a51c'/%3E%3C/svg%3E">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/styles.css">
  <style>
    body {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }
    .auth-card {
      width: 100%;
      max-width: 380px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 32px 28px;
      position: relative;
      overflow: hidden;
    }
    .auth-card::after {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--brand), var(--brand-hover));
    }
    .auth-logo {
      text-align: center;
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 4px;
      display: flex; align-items: center; justify-content: center; gap: 8px;
    }
    .auth-logo .dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--brand); box-shadow: 0 0 12px var(--brand-glow);
    }
    .auth-sub {
      text-align: center;
      font-size: 12px;
      color: var(--text-sec);
      margin-bottom: 24px;
    }
    .auth-tabs { display: flex; gap: 4px; background: var(--surface-2); border-radius: var(--radius-sm); padding: 3px; margin-bottom: 20px; }
    .auth-tab {
      flex: 1; text-align: center; padding: 8px; border-radius: 5px;
      font-size: 12px; font-weight: 600; color: var(--text-sec); cursor: pointer;
      transition: all var(--t-fast) var(--ease);
    }
    .auth-tab.active { background: var(--brand-soft); color: var(--brand-hover); }
    .auth-field { margin-bottom: 14px; }
    .auth-field label { display: block; font-size: 11px; color: var(--text-sec); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.3px; }
    .auth-field input {
      width: 100%; padding: 10px 12px; border-radius: var(--radius-sm);
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
      font-size: 13px; font-family: var(--font); outline: none;
      transition: border-color var(--t-fast) var(--ease);
    }
    .auth-field input:focus { border-color: var(--brand); }
    .auth-error {
      font-size: 12px; color: var(--danger); margin-bottom: 12px; min-height: 16px;
    }
    .auth-submit { width: 100%; justify-content: center; margin-top: 4px; }
  </style>
</head>
<body>

<div class="auth-card">
  <div class="auth-logo"><span class="dot"></span> Finanças</div>
  <div class="auth-sub">Acesse sua conta para ver carteira, watchlists e alertas</div>

  <div class="auth-tabs">
    <div class="auth-tab active" id="tab-login" onclick="switchTab('login')">Entrar</div>
    <div class="auth-tab" id="tab-register" onclick="switchTab('register')">Criar conta</div>
  </div>

  <div class="auth-error" id="auth-error"></div>

  <form id="form-login" onsubmit="event.preventDefault(); doLogin();">
    <div class="auth-field">
      <label for="login-email">Email</label>
      <input id="login-email" type="email" required placeholder="voce@email.com" autocomplete="email">
    </div>
    <div class="auth-field">
      <label for="login-password">Senha</label>
      <input id="login-password" type="password" required placeholder="••••••••" autocomplete="current-password">
    </div>
    <button class="btn btn-primary auth-submit" type="submit">Entrar</button>
  </form>

  <form id="form-register" style="display:none;" onsubmit="event.preventDefault(); doRegister();">
    <div class="auth-field">
      <label for="reg-name">Nome</label>
      <input id="reg-name" required placeholder="Seu nome" autocomplete="name">
    </div>
    <div class="auth-field">
      <label for="reg-email">Email</label>
      <input id="reg-email" type="email" required placeholder="voce@email.com" autocomplete="email">
    </div>
    <div class="auth-field">
      <label for="reg-password">Senha</label>
      <input id="reg-password" type="password" required minlength="8" placeholder="mínimo 8 caracteres" autocomplete="new-password">
    </div>
    <button class="btn btn-primary auth-submit" type="submit">Criar conta</button>
  </form>
</div>

<script src="/static/icons.js"></script>
<script src="/static/api.js"></script>
<script>
function switchTab(tab) {
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
  document.getElementById('form-login').style.display = tab === 'login' ? 'block' : 'none';
  document.getElementById('form-register').style.display = tab === 'register' ? 'block' : 'none';
  document.getElementById('auth-error').textContent = '';
}

function redirectAfterAuth() {
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get('redirect');
  window.location.href = redirect || '/';
}

function showAuthError(msg) {
  document.getElementById('auth-error').textContent = msg;
}

async function doLogin() {
  showAuthError('');
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  try {
    const resp = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await resp.json();
    if (!resp.ok) { showAuthError(data.detail || 'Email ou senha incorretos'); return; }
    localStorage.setItem('token', data.access_token);
    redirectAfterAuth();
  } catch (e) {
    showAuthError('Erro de conexão. Tente novamente.');
  }
}

async function doRegister() {
  showAuthError('');
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  try {
    const resp = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map(d => d.mensagem || d).join('; ')
        : (data.detail || 'Não foi possível criar a conta');
      showAuthError(detail);
      return;
    }
    localStorage.setItem('token', data.access_token);
    redirectAfterAuth();
  } catch (e) {
    showAuthError('Erro de conexão. Tente novamente.');
  }
}

// Se já está logado, não faz sentido mostrar a tela de login de novo
if (getToken()) redirectAfterAuth();
</script>
</body>
</html>
```

- [ ] **Step 2: Verificar manualmente**

Run: servidor já rodando (Task 5), abra `http://127.0.0.1:8000/static/login.html`.
Expected: cartão centralizado, tema dark+dourado, tabs "Entrar"/"Criar conta" funcionam. Crie uma conta nova → deve redirecionar pra `/` com token salvo (confirme em DevTools → Application → Local Storage).
Tente logar com senha errada → mensagem de erro em vermelho aparece, sem reload da página.

- [ ] **Step 3: Commit**

```bash
git add app/static/login.html
git commit -m "feat(frontend): adiciona página de login/registro real"
```

---

## Task 7: `watchlists.html` — trocar auto-login pela tela de login real

**Files:**
- Modify: `app/static/watchlists.html`

**Interfaces:**
- Consumes: `requireAuth()` de `api.js` (Task 5), `/static/login.html` (Task 6).

- [ ] **Step 1: Remover o auto-login hardcoded**

Em `app/static/watchlists.html`, substitua (linhas 197-217):

```js
let token = localStorage.getItem('token');
let currentWlId = null;
let wlData = [];

async function autoLogin() {
  if (!token) {
    try {
      const r = await fetch('/auth/login', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({email:'test@test.com', password:'12345678'})
      });
      if (r.ok) { const d = await r.json(); token = d.access_token; localStorage.setItem('token', token); }
    } catch(e) {}
  }
  if (token) carregarTudo();
  else {
    const area = document.getElementById('items-area');
    area.innerHTML = `<div class="loading-state"><span data-icon="lock" data-icon-size="16"></span><span>Faça login para acessar suas watchlists</span></div>`;
    hydrateIcons(area);
  }
}
```

por:

```js
let token = null;
let currentWlId = null;
let wlData = [];
```

- [ ] **Step 2: Trocar o disparo final do script**

Substitua (linha 370):

```js
document.addEventListener('DOMContentLoaded', autoLogin);
```

por:

```js
document.addEventListener('DOMContentLoaded', () => {
  token = requireAuth();
  if (token) carregarTudo();
});
```

(`requireAuth()` já redireciona para `/static/login.html` e retorna `null` se não houver token — quando isso acontece, a navegação já está em andamento e não precisamos fazer mais nada nesta página.)

- [ ] **Step 3: Verificar manualmente**

Run: abra `http://127.0.0.1:8000/static/watchlists.html` em uma aba anônima (sem token salvo).
Expected: redireciona para `/static/login.html?redirect=%2Fstatic%2Fwatchlists.html`. Logue → volta pra watchlists e carrega normalmente. Crie uma watchlist, adicione um ticker, remova — tudo deve continuar funcionando como antes (a única mudança é como o token é obtido).

- [ ] **Step 4: Commit**

```bash
git add app/static/watchlists.html
git commit -m "fix(frontend): watchlists.html usa tela de login real em vez de conta demo"
```

---

## Task 8: `alertas.html` — corrigir auto-login que derruba sessão real + falso "sucesso"

**Files:**
- Modify: `app/static/alertas.html`

**Interfaces:**
- Consumes: `requireAuth()` de `api.js` (Task 5).

- [ ] **Step 1: Trocar a inicialização do token**

Substitua (linha 165):

```js
let token = localStorage.getItem('token');
```

por:

```js
let token = null;
```

- [ ] **Step 2: Corrigir `criarAlerta()` para checar a resposta**

Substitua (linhas 222-239):

```js
async function criarAlerta() {
  if (!token) { showAlert('Faça login primeiro', 'Atenção'); return; }
  const ticker = document.getElementById('new-ticker').value.trim().toUpperCase();
  const direction = document.getElementById('new-direction').value;
  const target = parseFloat(document.getElementById('new-target').value.replace(',','.'));
  if (!ticker || !target) { showAlert('Preencha ticker e preço', 'Atenção'); return; }

  try {
    await fetch(`/me/alerts?ticker=${ticker}&target_price=${target}&direction=${direction}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    document.getElementById('new-ticker').value = '';
    document.getElementById('new-target').value = '';
    showToast('Alerta criado', 'success');
    carregarAlertas();
  } catch(e) { showAlert('Erro ao criar alerta: ' + e.message, 'Erro'); }
}
```

por:

```js
async function criarAlerta() {
  if (!token) { showAlert('Faça login primeiro', 'Atenção'); return; }
  const ticker = document.getElementById('new-ticker').value.trim().toUpperCase();
  const direction = document.getElementById('new-direction').value;
  const target = parseFloat(document.getElementById('new-target').value.replace(',','.'));
  if (!ticker || !target) { showAlert('Preencha ticker e preço', 'Atenção'); return; }

  try {
    const r = await fetch(`/me/alerts?ticker=${ticker}&target_price=${target}&direction=${direction}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      showAlert(err.detail || 'Erro ao criar alerta', 'Erro');
      return;
    }
    document.getElementById('new-ticker').value = '';
    document.getElementById('new-target').value = '';
    showToast('Alerta criado', 'success');
    carregarAlertas();
  } catch(e) { showAlert('Erro ao criar alerta: ' + e.message, 'Erro'); }
}
```

- [ ] **Step 3: Remover o `autoLogin()` hardcoded**

Substitua (linhas 271-287):

```js
async function autoLogin() {
  try {
    const r = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@test.com', password: '12345678' })
    });
    if (r.ok) {
      const d = await r.json();
      token = d.access_token;
      localStorage.setItem('token', token);
    }
  } catch(e) {}
  carregarAlertas();
}

document.addEventListener('DOMContentLoaded', autoLogin);
```

por:

```js
document.addEventListener('DOMContentLoaded', () => {
  token = requireAuth();
  if (token) carregarAlertas();
});
```

- [ ] **Step 4: Verificar manualmente**

Run: abra `/static/alertas.html` logado (de uma sessão já autenticada via login.html). Crie um alerta com ticker inválido (ex: `***`) → deve aparecer alerta de erro real (422 do backend), **não** "Alerta criado". Crie um alerta válido → some normalmente.

Confirme também que abrir `/static/alertas.html` **não desloga** uma sessão real: logue como um usuário de teste em `/static/login.html`, abra `/static/perfil.html` (mostra seu nome), depois abra `/static/alertas.html`, volte pra `/static/perfil.html` → deve continuar mostrando o mesmo usuário (antes, voltava pro `test@test.com`).

- [ ] **Step 5: Commit**

```bash
git add app/static/alertas.html
git commit -m "fix(frontend): alertas.html para de derrubar sessão real e de mentir sucesso em erro"
```

---

## Task 9: `perfil.html` — login real + "Editar Perfil"/"Alterar Senha" de verdade

**Files:**
- Modify: `app/static/perfil.html`

**Interfaces:**
- Consumes: `requireAuth()`/`authHeaders()` de `api.js` (Task 5), `PATCH /auth/me`, `POST /auth/change-password` (Task 4).

- [ ] **Step 1: Trocar o auto-login por `requireAuth()`**

Substitua o início de `carregarPerfil()` (linhas 128-151):

```js
async function carregarPerfil() {
  const area = document.getElementById('profile-area');
  let token = localStorage.getItem('token');

  if (!token) {
    try {
      const r = await fetch('/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email: 'test@test.com', password: '12345678'})
      });
      if (r.ok) {
        const d = await r.json();
        token = d.access_token;
        localStorage.setItem('token', token);
      }
    } catch(e) {}
  }

  if (!token) {
    area.innerHTML = `<div class="loading-state"><span data-icon="lock" data-icon-size="16"></span><span>Faça login para ver seu perfil</span></div>`;
    hydrateIcons(area);
    return;
  }

  area.innerHTML = '<div class="loading-state"><span class="spinner"></span><span>Carregando…</span></div>';
```

por:

```js
async function carregarPerfil() {
  const area = document.getElementById('profile-area');
  const token = requireAuth();
  if (!token) return; // requireAuth() já redirecionou para o login

  area.innerHTML = '<div class="loading-state"><span class="spinner"></span><span>Carregando…</span></div>';
```

(O restante de `carregarPerfil()`, que busca `/auth/me`, `/me/watchlists` e `/me/alerts` com esse `token`, continua igual — só remove a declaração duplicada de `token` mais abaixo na função, já que agora é `const` no topo.)

- [ ] **Step 2: Implementar `editarPerfil()` de verdade**

Substitua (linhas 239-245):

```js
function editarPerfil(nomeAtual) {
  showPrompt('Editar Perfil', 'Novo nome', nomeAtual).then(nome => {
    if (!nome) return;
    showToast('Nome atualizado para: ' + nome, 'success');
    setTimeout(() => location.reload(), 600);
  });
}
```

por:

```js
async function editarPerfil(nomeAtual) {
  const nome = await showPrompt('Editar Perfil', 'Novo nome', nomeAtual);
  if (!nome) return;
  try {
    const r = await fetch('/auth/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ name: nome }),
    });
    const data = await r.json();
    if (!r.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(d => d.mensagem || d).join('; ') : data.detail;
      showAlert(detail || 'Não foi possível atualizar o perfil', 'Erro');
      return;
    }
    showToast('Nome atualizado para: ' + data.name, 'success');
    setTimeout(() => location.reload(), 600);
  } catch (e) {
    showAlert('Erro de conexão: ' + e.message, 'Erro');
  }
}
```

- [ ] **Step 3: Implementar `alterarSenha()` de verdade**

Substitua (linhas 247-255):

```js
async function alterarSenha() {
  const atual = await showPrompt('Alterar Senha', 'Senha atual');
  if (!atual) return;
  const nova = await showPrompt('Alterar Senha', 'Nova senha (mín. 8 caracteres)');
  if (!nova || nova.length < 8) { showAlert('Senha muito curta (mínimo 8 caracteres)', 'Validação'); return; }
  const confirma = await showPrompt('Alterar Senha', 'Confirme a nova senha');
  if (nova !== confirma) { showAlert('Senhas não conferem', 'Erro'); return; }
  showToast('Senha alterada com sucesso!', 'success');
}
```

por:

```js
async function alterarSenha() {
  const atual = await showPrompt('Alterar Senha', 'Senha atual');
  if (!atual) return;
  const nova = await showPrompt('Alterar Senha', 'Nova senha (mín. 8 caracteres)');
  if (!nova || nova.length < 8) { showAlert('Senha muito curta (mínimo 8 caracteres)', 'Validação'); return; }
  const confirma = await showPrompt('Alterar Senha', 'Confirme a nova senha');
  if (nova !== confirma) { showAlert('Senhas não conferem', 'Erro'); return; }

  try {
    const r = await fetch('/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ current_password: atual, new_password: nova }),
    });
    const data = await r.json();
    if (!r.ok) { showAlert(data.detail || 'Não foi possível trocar a senha', 'Erro'); return; }
    showToast('Senha alterada com sucesso!', 'success');
  } catch (e) {
    showAlert('Erro de conexão: ' + e.message, 'Erro');
  }
}
```

- [ ] **Step 4: Fazer `logout()` redirecionar pro login**

Substitua (linhas 257-263):

```js
async function logout() {
  const ok = await showConfirm('Sair da conta?', 'Sair', { danger: true });
  if (!ok) return;
  localStorage.removeItem('token');
  showToast('Desconectado', 'success');
  setTimeout(() => location.reload(), 600);
}
```

por:

```js
async function logout() {
  const ok = await showConfirm('Sair da conta?', 'Sair', { danger: true });
  if (!ok) return;
  localStorage.removeItem('token');
  showToast('Desconectado', 'success');
  setTimeout(() => { window.location.href = '/static/login.html'; }, 600);
}
```

- [ ] **Step 5: Verificar manualmente**

Run: logue em `/static/login.html`, vá em `/static/perfil.html`. Clique "Editar Perfil", troque o nome → nome muda de verdade (confirme recarregando a página). Clique "Alterar Senha" com a senha atual errada → mensagem de erro real ("Senha atual incorreta"); com a senha certa → sucesso, e confira que o login com a senha nova funciona (a antiga não funciona mais). Clique "Sair" → vai para `/static/login.html`.

- [ ] **Step 6: Commit**

```bash
git add app/static/perfil.html
git commit -m "fix(frontend): perfil.html edita nome e troca senha de verdade"
```

---

## Task 10: `carteira.html` — persistir no backend (`/me/portfolio`) + corrigir DY Médio hardcoded

**Files:**
- Modify: `app/static/carteira.html`

**Interfaces:**
- Consumes: `requireAuth()`/`authHeaders()` de `api.js` (Task 5), `GET/POST/DELETE /me/portfolio` (Task 3).
- Produces: nada novo consumido por outras tasks (Task 11 faz o dashboard usar o mesmo endpoint, mas com sua própria chamada).

A página inteira troca de fonte de dados (localStorage → backend); o HTML/CSS não muda, só o `<script>`.

- [ ] **Step 1: Substituir o `<script>` inteiro de `carteira.html`**

Substitua todo o bloco de script (linhas 248-402, entre `<script src="/static/api.js"></script>` e `</script>` final) por:

```html
<script src="/static/icons.js"></script>
<script src="/static/api.js"></script>
<script>
const COLORS = ['gold','blue','green','orange','violet','teal'];
const ICON_MAP = { 'gold':'droplets','blue':'factory','green':'bank','orange':'bank','violet':'spark','teal':'zap' };
const NAMES = { 'gold':'Petrobras','blue':'Vale','green':'Itaú','orange':'Banco do Brasil','violet':'Outro','teal':'Energia' };

let token = null;

async function carregarPortfolio() {
  const r = await fetch('/me/portfolio', { headers: authHeaders() });
  if (!r.ok) throw new Error('Não foi possível carregar a carteira');
  const data = await r.json();
  // Mapeia quantity/avg_cost (nomes do backend) pra qty/cost (nomes usados no render)
  return data.positions.map(p => ({ id: p.id, ticker: p.ticker, qty: p.quantity, cost: p.avg_cost }));
}

function renderCard(id, ticker, qty, cost, colorIdx, q, totalVal) {
  const color = COLORS[colorIdx % COLORS.length];
  const iconName = ICON_MAP[color] || 'trendingUp';
  const price = q ? q.price : 0;
  const val = qty * price;
  const costTotal = qty * cost;
  const pl = val - costTotal;
  const plPct = cost > 0 ? ((price - cost) / cost) * 100 : 0;
  const pct = totalVal > 0 ? (val / totalVal) * 100 : 0;

  return `<div class="card pos-card" data-ticker="${ticker}" onclick="window.location='/static/relatorio.html?${ticker}'">
    <button class="delete-btn" onclick="event.stopPropagation();removerAtivo('${id}','${ticker}')" aria-label="Remover ${ticker}">${icon('x', { size: 12 })}</button>
    <div class="card-top">
      <div class="card-company">
        <div class="icon-box icon-${color}">${icon(iconName, { size: 18 })}</div>
        <div class="card-name"><h3>${ticker}</h3><div class="sub">${NAMES[color] || ticker} · ${qty} ações</div></div>
      </div>
      <span class="card-badge ${pl >= 0 ? 'up' : 'down'}">${pl >= 0 ? '▲' : '▼'} ${Math.abs(plPct).toFixed(1)}%</span>
    </div>
    <div class="card-mid">
      <div class="card-value">${formatMoney(val)}</div>
      <div class="card-qty">${pct.toFixed(0)}%</div>
    </div>
    <div class="pct-bar"><div style="width:${Math.max(pct,5)}%;"></div></div>
    <div class="card-info-row">
      <span>Custo <span class="val">${formatMoney(costTotal)}</span></span>
      <span>Preço <span class="val">${formatMoney(price)}</span></span>
      <span>Lucro <span class="val" style="color:${pl >= 0 ? 'var(--success)' : 'var(--danger)'}">${pl >= 0 ? '+' : '-'}${formatMoney(Math.abs(pl))}</span></span>
    </div>
  </div>`;
}

async function carregarTudo() {
  const grid = document.getElementById('positions-grid');
  let portfolio;
  try {
    portfolio = await carregarPortfolio();
  } catch (e) {
    grid.innerHTML = `<div class="loading-state" style="width:100%;grid-column:1/-1;"><span data-icon="error" data-icon-size="16"></span><span>${escapeHtml(e.message)}</span></div>`;
    hydrateIcons(grid);
    return;
  }

  if (!portfolio || portfolio.length === 0) {
    grid.innerHTML = `<div class="loading-state" style="width:100%;grid-column:1/-1;"><span data-icon="info" data-icon-size="16"></span><span>Carteira vazia. Clique em "+ Novo Ativo" para começar.</span></div>`;
    hydrateIcons(grid);
    document.getElementById('total-positions').textContent = '0';
    document.getElementById('total-value').textContent = formatMoney(0);
    return;
  }

  let totalVal = 0, totalCost = 0, totalShares = 0;
  const quotes = {};
  const dyByTicker = {};

  for (const item of portfolio) {
    try {
      const q = await apiGet(`/api/quote/${item.ticker}`);
      quotes[item.ticker] = q;
      totalVal += q.price * item.qty;
    } catch(e) {
      quotes[item.ticker] = null;
    }
    totalCost += item.qty * item.cost;
    totalShares += item.qty;
  }

  grid.innerHTML = portfolio.map((item, i) => {
    return renderCard(item.id, item.ticker, item.qty, item.cost, i, quotes[item.ticker], totalVal);
  }).join('');
  hydrateIcons(grid);

  const totalPL = totalVal - totalCost;
  const totalPct = totalCost > 0 ? (totalPL / totalCost) * 100 : 0;
  document.getElementById('total-value').textContent = formatMoney(totalVal);
  const returnEl = document.getElementById('total-return');
  returnEl.innerHTML = `${totalPL >= 0 ? '▲' : '▼'} ${Math.abs(totalPct).toFixed(1)}%`;
  returnEl.className = `pct ${totalPL >= 0 ? 'up' : 'down'}`;
  document.getElementById('total-profit').textContent = `${totalPL >= 0 ? '+' : '-'}${formatMoney(Math.abs(totalPL))}`;
  document.getElementById('total-shares').textContent = totalShares;
  const profitAbs = document.getElementById('total-profit-abs');
  profitAbs.textContent = `${totalPL >= 0 ? '+' : '-'}${formatMoney(Math.abs(totalPL))}`;
  profitAbs.style.color = totalPL >= 0 ? 'var(--success)' : 'var(--danger)';
  document.getElementById('total-positions').textContent = portfolio.length;

  const allocBar = document.getElementById('allocation-bar');
  const SECTOR_COLORS = ['#d6a51c','#3b82f6','#10b981','#f97316','#8b5cf6','#14b8a6'];
  allocBar.innerHTML = portfolio.map((item, i) => {
    const pct = totalVal > 0 ? ((quotes[item.ticker]?.price || 0) * item.qty / totalVal) * 100 : 0;
    return `<div style="width:${Math.max(pct, 5)}%;background:${SECTOR_COLORS[i % SECTOR_COLORS.length]};" data-ticker="${item.ticker}" title="${item.ticker}: ${pct.toFixed(1)}%"></div>`;
  }).join('');

  // DY Médio: média do dividend_yield de TODOS os ativos da carteira
  // (antes era hardcoded em PETR4, ignorando os ativos reais do usuário)
  const dyResults = await Promise.allSettled(
    portfolio.map(item => apiGet(`/api/quote/${item.ticker}/statistics`).catch(() => null))
  );
  const yields = dyResults
    .map(r => r.status === 'fulfilled' ? r.value : null)
    .filter(s => s && s.dividend_yield != null && !isNaN(s.dividend_yield))
    .map(s => s.dividend_yield);
  if (yields.length > 0) {
    const avgDy = (yields.reduce((a, b) => a + b, 0) / yields.length) * 100;
    document.getElementById('avg-dy').textContent = `${avgDy.toFixed(1)}%`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  token = requireAuth();
  if (token) carregarTudo();
});

// Modal
function abrirModal() {
  const overlay = document.getElementById('modal-overlay');
  overlay.classList.add('show');
  document.getElementById('modal-ticker').value = '';
  document.getElementById('modal-qty').value = '';
  document.getElementById('modal-cost').value = '';
  setTimeout(() => document.getElementById('modal-ticker').focus(), 100);
}

function fecharModal() {
  document.getElementById('modal-overlay').classList.remove('show');
}

async function confirmarModal() {
  const ticker = document.getElementById('modal-ticker').value.trim().toUpperCase();
  const qtd = parseInt(document.getElementById('modal-qty').value);
  const custo = parseFloat(document.getElementById('modal-cost').value.replace(',','.'));
  if (!ticker || !qtd || qtd < 1 || !custo || custo <= 0) {
    showAlert('Preencha todos os campos corretamente', 'Validação');
    return;
  }
  fecharModal();
  try {
    const r = await fetch(`/me/portfolio?ticker=${ticker}&quantity=${qtd}&avg_cost=${custo}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      showAlert(err.detail || 'Erro ao adicionar ativo', 'Erro');
      return;
    }
    showToast(`${ticker} adicionado à carteira`, 'success');
    carregarTudo();
  } catch (e) {
    showAlert('Erro de conexão: ' + e.message, 'Erro');
  }
}

function removerAtivo(positionId, ticker) {
  showConfirm(`Remover ${ticker} da carteira?`, 'Excluir', { danger: true }).then(async ok => {
    if (!ok) return;
    try {
      const r = await fetch(`/me/portfolio/${positionId}`, { method: 'DELETE', headers: authHeaders() });
      if (!r.ok) { showAlert('Erro ao remover ativo', 'Erro'); return; }
      showToast(`${ticker} removido da carteira`, 'success');
      carregarTudo();
    } catch (e) {
      showAlert('Erro de conexão: ' + e.message, 'Erro');
    }
  });
}
</script>
```

- [ ] **Step 2: Verificar manualmente**

Run: logue, abra `/static/carteira.html` (vazio na primeira vez, pois a carteira agora é por usuário). Clique "+ Novo Ativo", adicione PETR4/100/38.50 → aparece card real. Adicione mais 2-3 ativos de setores diferentes. Recarregue a página (F5) → posições continuam lá (prova de que persiste no backend, não mais no localStorage). Abra em outro navegador/aba anônima logando com a mesma conta → mesma carteira aparece. Confira "DY Médio" no resumo: deve refletir a média dos ativos que você realmente adicionou, não sempre PETR4. Remova um ativo → confirma e desaparece.

- [ ] **Step 3: Commit**

```bash
git add app/static/carteira.html
git commit -m "feat(frontend): carteira.html persiste no backend, corrige DY Médio hardcoded"
```

---

## Task 11: `dashboard.html` — widgets de carteira buscam do backend (não mais localStorage)

**Files:**
- Modify: `app/static/dashboard.html`

**Interfaces:**
- Consumes: `getToken()`/`authHeaders()` de `api.js` (Task 5), `GET /me/portfolio` (Task 3).

O Dashboard continua acessível sem login (IBOVESPA e a tabela "Principais Ativos" são uma vitrine fixa, não dependem de usuário) — só os widgets "Valor da Carteira" e "Distribuição da Carteira" passam a depender de estar logado, com um estado visual próprio pra visitante anônimo (em vez de inventar dados fake de localStorage).

- [ ] **Step 1: Trocar `getPortfolio()` (localStorage) por versão assíncrona via backend**

Substitua (linhas 154-164):

```js
function getPortfolio() {
  if (portfolioCache) return portfolioCache;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    portfolioCache = raw ? JSON.parse(raw) : DEFAULT_TICKERS.map(t => ({ ticker: t, qty: 100, cost: 30 }));
  } catch(e) {
    portfolioCache = [];
  }
  return portfolioCache;
}
```

por:

```js
async function getPortfolio() {
  if (portfolioCache !== undefined) return portfolioCache;
  const token = getToken();
  if (!token) { portfolioCache = null; return null; } // null = visitante não logado
  try {
    const r = await fetch('/me/portfolio', { headers: authHeaders() });
    if (!r.ok) { portfolioCache = []; return portfolioCache; }
    const data = await r.json();
    portfolioCache = data.positions.map(p => ({ ticker: p.ticker, qty: p.quantity, cost: p.avg_cost }));
  } catch (e) {
    portfolioCache = [];
  }
  return portfolioCache;
}
```

E troque a declaração inicial (linha 135):

```js
let portfolioCache = null;
```

por:

```js
let portfolioCache = undefined; // undefined = ainda não buscou; null = visitante sem login; [] = logado sem posições
```

- [ ] **Step 2: `computePortfolioStats()` passa a receber o portfolio já carregado**

Substitua (linhas 295-315):

```js
async function computePortfolioStats() {
  const portfolio = getPortfolio();
  if (!portfolio || portfolio.length === 0) return null;

  const quotes = await Promise.all(portfolio.map(p =>
    apiGet(`/api/quote/${p.ticker}`).catch(() => null)
  ));

  let totalValue = 0, totalCost = 0, totalShares = 0;
  for (let i = 0; i < portfolio.length; i++) {
    const q = quotes[i];
    if (q && q.price) totalValue += q.price * portfolio[i].qty;
    totalCost += portfolio[i].qty * portfolio[i].cost;
    totalShares += portfolio[i].qty;
  }

  const totalPL = totalValue - totalCost;
  const totalPct = totalCost > 0 ? (totalPL / totalCost) * 100 : 0;

  return { totalValue, totalCost, totalShares, totalPct, positionCount: portfolio.length, quotes, portfolio };
}
```

por:

```js
async function computePortfolioStats(portfolio) {
  if (!portfolio || portfolio.length === 0) return null;

  const quotes = await Promise.all(portfolio.map(p =>
    apiGet(`/api/quote/${p.ticker}`).catch(() => null)
  ));

  let totalValue = 0, totalCost = 0, totalShares = 0;
  for (let i = 0; i < portfolio.length; i++) {
    const q = quotes[i];
    if (q && q.price) totalValue += q.price * portfolio[i].qty;
    totalCost += portfolio[i].qty * portfolio[i].cost;
    totalShares += portfolio[i].qty;
  }

  const totalPL = totalValue - totalCost;
  const totalPct = totalCost > 0 ? (totalPL / totalCost) * 100 : 0;

  return { totalValue, totalCost, totalShares, totalPct, positionCount: portfolio.length, quotes, portfolio };
}
```

(`computePortfolioStats` agora é uma função pura sobre o array que recebe — quem decide *de onde* vem o array, e o que fazer se for `null`, é cada chamador, nas Steps 3 e 4.)

- [ ] **Step 3: Card "Valor da Carteira" com estado de "faça login"**

Substitua o início de `carregarCards()` (linhas 179-216), trocando só a parte do Card 2:

```js
async function carregarCards(statistics) {
  const container = document.getElementById('cards-container');

  const [idxQ, portfolioStats] = await Promise.allSettled([
    apiGet(`/api/quote/${INDEX_PROXY}`).catch(() => null),
    computePortfolioStats(),
  ]);

  const idx = idxQ.status === 'fulfilled' ? idxQ.value : null;
  const ps  = portfolioStats.status === 'fulfilled' ? portfolioStats.value : null;

  container.innerHTML = '';

  // Card 1: IBOVESPA (via BOVA11)
  if (idx && idx.price != null) {
    container.insertAdjacentHTML('beforeend', cardHTML({
      iconName: 'trendingUp',
      label: 'IBOVESPA',
      value: idx.price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      sub: 'Principal índice da B3 (via BOVA11)',
      change: idx.change_percent || 0,
    }));
  } else {
    container.insertAdjacentHTML('beforeend', cardErrorHTML('IBOVESPA', 'trendingUp'));
  }

  // Card 2: Carteira
  if (ps && ps.totalShares > 0) {
    container.insertAdjacentHTML('beforeend', cardHTML({
      iconName: 'wallet',
      label: 'Valor da Carteira',
      value: formatMoney(ps.totalValue),
      sub: `${ps.positionCount} ativos · ${ps.totalShares.toLocaleString('pt-BR')} ações`,
      change: ps.totalPct,
    }));
  } else {
    container.insertAdjacentHTML('beforeend', cardErrorHTML('Carteira', 'wallet'));
  }
```

por:

```js
async function carregarCards(statistics) {
  const container = document.getElementById('cards-container');

  const portfolio = await getPortfolio();
  const [idxQ, portfolioStats] = await Promise.allSettled([
    apiGet(`/api/quote/${INDEX_PROXY}`).catch(() => null),
    portfolio && portfolio.length > 0 ? computePortfolioStats(portfolio) : Promise.resolve(null),
  ]);

  const idx = idxQ.status === 'fulfilled' ? idxQ.value : null;
  const ps  = portfolioStats.status === 'fulfilled' ? portfolioStats.value : null;

  container.innerHTML = '';

  // Card 1: IBOVESPA (via BOVA11)
  if (idx && idx.price != null) {
    container.insertAdjacentHTML('beforeend', cardHTML({
      iconName: 'trendingUp',
      label: 'IBOVESPA',
      value: idx.price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      sub: 'Principal índice da B3 (via BOVA11)',
      change: idx.change_percent || 0,
    }));
  } else {
    container.insertAdjacentHTML('beforeend', cardErrorHTML('IBOVESPA', 'trendingUp'));
  }

  // Card 2: Carteira (3 estados: não logado / vazia / com posições)
  if (ps && ps.totalShares > 0) {
    container.insertAdjacentHTML('beforeend', cardHTML({
      iconName: 'wallet',
      label: 'Valor da Carteira',
      value: formatMoney(ps.totalValue),
      sub: `${ps.positionCount} ativos · ${ps.totalShares.toLocaleString('pt-BR')} ações`,
      change: ps.totalPct,
    }));
  } else if (portfolio === null) {
    container.insertAdjacentHTML('beforeend', cardLoginHTML('Carteira', 'wallet'));
  } else {
    container.insertAdjacentHTML('beforeend', cardErrorHTML('Carteira', 'wallet'));
  }
```

- [ ] **Step 4: Adicionar o helper `cardLoginHTML`**

Adicione depois de `cardErrorHTML` (linha 271):

```js
function cardLoginHTML(label, iconName) {
  return `<div class="card" style="cursor:pointer;" onclick="window.location='/static/login.html'" role="button" tabindex="0">
    <div class="card-icon">${icon(iconName, { size: 18 })}</div>
    <div class="card-label">${escapeHtml(label)}</div>
    <div class="card-value" style="color:var(--brand-hover);font-size:15px;">Entrar</div>
    <div class="card-sub">Faça login para ver sua carteira</div>
  </div>`;
}
```

- [ ] **Step 5: `carregarDistribuicao()` com estado de "faça login"**

Substitua (linhas 379-389):

```js
async function carregarDistribuicao() {
  const ps = await computePortfolioStats().catch(() => null);
  const body = document.getElementById('alloc-body');
  const sub = document.getElementById('alloc-sub');

  if (!ps || ps.totalValue <= 0) {
    sub.textContent = 'Adicione ativos à carteira para ver a distribuição';
    body.innerHTML = `<div class="loading-state"><span data-icon="info" data-icon-size="16"></span><span>Carteira vazia. Vá em Carteira para começar.</span></div>`;
    hydrateIcons(body);
    return;
  }
```

por:

```js
async function carregarDistribuicao() {
  const body = document.getElementById('alloc-body');
  const sub = document.getElementById('alloc-sub');
  const portfolio = await getPortfolio();

  if (portfolio === null) {
    sub.textContent = 'Faça login para ver a distribuição da sua carteira';
    body.innerHTML = `<div class="loading-state"><span data-icon="lock" data-icon-size="16"></span><span><a href="/static/login.html" style="color:var(--brand-hover);">Faça login</a> para acompanhar sua carteira</span></div>`;
    hydrateIcons(body);
    return;
  }

  const ps = portfolio.length > 0 ? await computePortfolioStats(portfolio).catch(() => null) : null;

  if (!ps || ps.totalValue <= 0) {
    sub.textContent = 'Adicione ativos à carteira para ver a distribuição';
    body.innerHTML = `<div class="loading-state"><span data-icon="info" data-icon-size="16"></span><span>Carteira vazia. Vá em Carteira para começar.</span></div>`;
    hydrateIcons(body);
    return;
  }
```

(o resto da função, que monta as barras de setor a partir de `ps`, continua igual.)

- [ ] **Step 6: Verificar manualmente**

Run: abra `/` em aba anônima (sem login) → cards de IBOVESPA e tabela aparecem normalmente; card "Carteira" mostra "Entrar" e o gráfico de distribuição mostra "Faça login para acompanhar sua carteira", ambos clicáveis levando ao login. Logue e adicione ativos em `/static/carteira.html` (Task 10), volte pro dashboard → card "Valor da Carteira" e o gráfico de distribuição agora mostram os dados reais da sua carteira.

- [ ] **Step 7: Commit**

```bash
git add app/static/dashboard.html
git commit -m "fix(frontend): dashboard busca carteira do backend, remove fallback fake de localStorage"
```

---

## Task 12: Chart.js — gráfico de preço histórico (linha, com dourado) no Dashboard

**Files:**
- Modify: `app/static/dashboard.html`

**Interfaces:**
- Consumes: Chart.js 4.x via CDN (novo).
- Produces: `window._priceChart` (instância Chart.js) — só usada dentro desta página.

- [ ] **Step 1: Confirmar a altura do container do gráfico**

Run: `grep -n "chart-wrap\|chart-box" app/static/styles.css`
Expected: alguma regra com `height` ou `min-height` pra `.chart-wrap`. Se não houver altura fixa, adicione em `styles.css`:

```css
.chart-wrap { position: relative; height: 220px; }
```

(Chart.js com `maintainAspectRatio: false` precisa de um container com altura definida, senão o canvas cresce indefinidamente.)

- [ ] **Step 2: Carregar Chart.js via CDN**

Em `app/static/dashboard.html`, depois de `<script src="/static/api.js?v=2"></script>` (linha 127), adicione:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
```

- [ ] **Step 3: Trocar o miolo de `renderChart()` pra desenhar com Chart.js**

Substitua o trecho que monta o HTML das barras (dentro de `renderChart`, dentro do `try`, dado por `let html = ''` até `container.innerHTML = html;`):

```js
    let html = '';
    for (let i = 0; i < last12.length; i++) {
      const pct = ((last12[i].close - min) / range);
      const px = Math.max(pct * chartH * 0.8, 8);
      const mi = (now.getMonth() - (last12.length - 1 - i) + 12) % 12;
      const dateStr = last12[i].date ? last12[i].date.substring(0,7) : '';
      const divVal = divsByMonth[dateStr] || 0;

      html += `<div class="chart-col">
        <div class="chart-value-label">${formatMoney(last12[i].close)}</div>
        ${window._showDivs && divVal > 0 ? `<div style="color:var(--success);font-size:9px;margin-bottom:1px;">${formatMoney(divVal)}</div>` : ''}
        <div class="chart-bar" style="height:${px.toFixed(0)}px"></div>
        ${window._showDivs && divVal > 0 ? `<div style="height:3px;background:var(--success);border-radius:2px;width:60%;margin:1px 0;"></div>` : ''}
        <span class="chart-label">${months[mi]}</span>
      </div>`;
    }
    container.innerHTML = html;
```

por:

```js
    const labels = last12.map((c, i) => {
      const mi = (now.getMonth() - (last12.length - 1 - i) + 12) % 12;
      return months[mi];
    });
    const priceData = last12.map(c => c.close);
    const divData = last12.map(c => {
      const dateStr = c.date ? c.date.substring(0,7) : '';
      return divsByMonth[dateStr] || 0;
    });

    container.innerHTML = '<canvas id="price-chart"></canvas>';
    const ctx = document.getElementById('price-chart').getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, chartH || 220);
    gradient.addColorStop(0, 'rgba(214, 165, 28, 0.35)');
    gradient.addColorStop(1, 'rgba(214, 165, 28, 0)');

    const datasets = [{
      type: 'line',
      label: 'Preço',
      data: priceData,
      borderColor: '#d6a51c',
      backgroundColor: gradient,
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointBackgroundColor: '#d6a51c',
      pointHoverRadius: 5,
      borderWidth: 2,
      yAxisID: 'y',
    }];

    if (window._showDivs) {
      datasets.push({
        type: 'bar',
        label: 'Dividendos',
        data: divData,
        backgroundColor: 'rgba(45, 212, 110, 0.6)',
        borderRadius: 3,
        yAxisID: 'y1',
      });
    }

    if (window._priceChart) window._priceChart.destroy();
    window._priceChart = new Chart(ctx, {
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: window._showDivs, labels: { color: '#9191a6', font: { size: 11 } } },
          tooltip: {
            backgroundColor: '#1b1d25',
            borderColor: '#2b2d38',
            borderWidth: 1,
            titleColor: '#eaeaef',
            bodyColor: '#eaeaef',
            callbacks: {
              label: (ctx) => ctx.dataset.label === 'Preço'
                ? ` Preço: ${formatMoney(ctx.parsed.y)}`
                : ` Dividendos: ${formatMoney(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#9191a6', font: { size: 10 } } },
          y: {
            position: 'left',
            grid: { color: '#1e2028' },
            ticks: { color: '#9191a6', font: { size: 10 }, callback: (v) => formatMoney(v) },
          },
          y1: {
            display: !!window._showDivs,
            position: 'right',
            grid: { display: false },
            ticks: { color: '#9191a6', font: { size: 10 }, callback: (v) => formatMoney(v) },
          },
        },
      },
    });
```

- [ ] **Step 4: Verificar manualmente**

Run: abra `/`, o gráfico "Preço nos Últimos 12 Meses" deve renderizar como linha suave com área dourada preenchida, tooltip ao passar o mouse mostrando o preço formatado. Clique em "Preço+Div" → aparecem barras verdes de dividendos sobrepostas com eixo Y secundário; clique de novo pra voltar. Troque o ativo selecionado na tabela "Principais Ativos" → o gráfico re-renderiza pro novo ticker sem acumular gráficos fantasmas (confirme no DevTools que só existe 1 `<canvas>`).

- [ ] **Step 5: Commit**

```bash
git add app/static/dashboard.html app/static/styles.css
git commit -m "feat(frontend): substitui barras CSS por gráfico de linha Chart.js no dashboard"
```

---

## Task 13: Chart.js — distribuição setorial como doughnut

**Files:**
- Modify: `app/static/dashboard.html`

**Interfaces:**
- Consumes: Chart.js (já carregado na Task 12), `sectorValue`/`SECTOR_COLORS` já calculados em `carregarDistribuicao()`.

- [ ] **Step 1: Trocar o corpo de `carregarDistribuicao()` que desenha as barras**

Substitua o trecho final da função (a partir de `sub.textContent = ...Total...` até o fechamento do `.join('')`):

```js
  sub.textContent = `Distribuição por setor · Total ${formatMoney(ps.totalValue)}`;

  const items = Object.entries(sectorValue)
    .map(([sector, value]) => ({
      label: sector,
      value,
      pct: (value / ps.totalValue) * 100,
      color: SECTOR_COLORS[sector] || '#6b7280',
    }))
    .sort((a, b) => b.value - a.value);

  body.innerHTML = items.map(item => `
    <div class="bar-section">
      <div class="bar-row">
        <span class="bar-label">
          <span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${item.color};"></span>
          ${escapeHtml(item.label)}
        </span>
        <span class="bar-pct">${item.pct.toFixed(0)}%</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${item.pct.toFixed(1)}%;background:linear-gradient(90deg, ${item.color}, ${item.color}cc);"></div></div>
    </div>
  `).join('');
```

por:

```js
  sub.textContent = `Distribuição por setor · Total ${formatMoney(ps.totalValue)}`;

  const items = Object.entries(sectorValue)
    .map(([sector, value]) => ({
      label: sector,
      value,
      pct: (value / ps.totalValue) * 100,
      color: SECTOR_COLORS[sector] || '#6b7280',
    }))
    .sort((a, b) => b.value - a.value);

  body.innerHTML = `
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
      <div style="position:relative;width:140px;height:140px;flex-shrink:0;">
        <canvas id="sector-chart"></canvas>
      </div>
      <div style="flex:1;min-width:160px;">
        ${items.map(item => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:12px;">
            <span style="display:flex;align-items:center;gap:6px;color:var(--text-sec);">
              <span style="display:inline-block;width:9px;height:9px;border-radius:3px;background:${item.color};"></span>
              ${escapeHtml(item.label)}
            </span>
            <span style="font-family:var(--mono);color:var(--text);font-weight:600;">${item.pct.toFixed(0)}%</span>
          </div>
        `).join('')}
      </div>
    </div>`;

  const ctx = document.getElementById('sector-chart').getContext('2d');
  if (window._sectorChart) window._sectorChart.destroy();
  window._sectorChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: items.map(i => i.label),
      datasets: [{
        data: items.map(i => i.value),
        backgroundColor: items.map(i => i.color),
        borderColor: '#13151b',
        borderWidth: 2,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1b1d25',
          borderColor: '#2b2d38',
          borderWidth: 1,
          titleColor: '#eaeaef',
          bodyColor: '#eaeaef',
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${formatMoney(ctx.parsed)}`,
          },
        },
      },
    },
  });
```

- [ ] **Step 2: Verificar manualmente**

Run: com a carteira tendo ativos de pelo menos 2 setores (Task 10), abra `/` → "Distribuição da Carteira" mostra um doughnut colorido à esquerda e a legenda com percentuais à direita. Passe o mouse nas fatias → tooltip mostra valor em R$. Recarregue a página várias vezes → não deve haver erro de canvas duplicado no console.

- [ ] **Step 3: Commit**

```bash
git add app/static/dashboard.html
git commit -m "feat(frontend): substitui barras de distribuição setorial por doughnut Chart.js"
```

---

## Task 14: Limpeza de CSS/JS morto encontrada na auditoria

**Files:**
- Modify: `app/static/styles.css`
- Modify: `app/static/icons.js`

**Interfaces:** nenhuma (só remoção de código morto, sem mudar comportamento).

- [ ] **Step 1: Remover a linha de CSS inválida**

Em `app/static/styles.css`, remova a linha (perto do topo, dentro do bloco de comentário de fontes):

```css
@font-face-glyph-layout: latin;
```

(Não é uma propriedade CSS válida — resíduo de edição anterior, sem efeito.)

- [ ] **Step 2: Remover a duplicata de `escapeHtml`**

`escapeHtml` está definida tanto em `icons.js` quanto em `api.js` com o mesmo corpo. Como toda página carrega `icons.js` antes de `api.js`, a versão de `api.js` sempre prevalece. Remova a de `icons.js` (perto do final do arquivo):

```js
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
```

- [ ] **Step 3: Verificar manualmente**

Run: abra qualquer página (ex: `/static/watchlists.html`), confirme no console que não há erro `escapeHtml is not defined` (a versão de `api.js` continua disponível).

- [ ] **Step 4: Commit**

```bash
git add app/static/styles.css app/static/icons.js
git commit -m "chore(frontend): remove CSS inválido e escapeHtml duplicada"
```

---

## Task 15: Verificação final de ponta a ponta

**Files:** nenhum (só verificação manual + suíte automatizada).

- [ ] **Step 1: Suíte de backend completa**

Run: `.venv/bin/python -m pytest -q`
Expected: todos os testes passam (incluindo os novos de `test_portfolio.py`, `test_portfolio_service.py` e os 4 novos em `test_auth.py`).

Run: `.venv/bin/python -m ruff check app/ tests/`
Expected: `All checks passed!`

Run: `.venv/bin/python -m mypy --strict app/`
Expected: `Success: no issues found`

- [ ] **Step 2: Checklist manual no navegador (com o servidor rodando)**

Run: `.venv/bin/python -m uvicorn app.main:app --port 8000` (background), abra `http://127.0.0.1:8000/` numa aba anônima nova a cada item abaixo que mencionar "anônima":

- [ ] Aba anônima → Dashboard carrega sem login: IBOVESPA, tabela de ativos e gráfico de linha (Chart.js) aparecem; card "Carteira" e gráfico de distribuição mostram "Entrar"/"Faça login", ambos clicáveis.
- [ ] Clique em "Entrar" → vai pra `/static/login.html`; crie uma conta nova pela aba "Criar conta".
- [ ] Após criar conta, é redirecionado pro Dashboard logado; sidebar sem o botão de tema (removido).
- [ ] `/static/carteira.html`: adicione 3+ ativos de setores diferentes; recarregue a página — posições persistem (backend, não localStorage). "DY Médio" reflete os ativos reais.
- [ ] Volte ao Dashboard: card "Valor da Carteira" e doughnut de distribuição agora mostram dados reais.
- [ ] `/static/watchlists.html`: crie uma watchlist, adicione e remova um ticker.
- [ ] `/static/alertas.html`: crie um alerta válido (sucesso) e um com ticker inválido como `***` (deve mostrar erro real, não "criado").
- [ ] `/static/comparar.html` e `/static/relatorio.html`: continuam funcionando como antes (não foram alterados nesta leva).
- [ ] `/static/perfil.html`: "Editar Perfil" muda o nome de verdade (confirme com F5); "Alterar Senha" com senha atual errada mostra erro real; com senha certa, funciona e a senha antiga deixa de logar.
- [ ] Clique "Sair" → vai pro login. Tente abrir `/static/watchlists.html` direto sem logar → redireciona pro login preservando `?redirect=`.
- [ ] Abra o DevTools Console em cada página visitada acima → zero erros JS (`ReferenceError`, `TypeError`, 404 de script).

- [ ] **Step 3: Atualizar a memória do projeto**

Depois de toda a checklist passar, atualize `[[financial-api-deploy-backlog]]` (memória) registrando: frontend conectado ao backend (auth real, carteira persistida, gráficos Chart.js), e que os itens de CI/deploy público continuam pendentes (fora do escopo desta leva).

