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
