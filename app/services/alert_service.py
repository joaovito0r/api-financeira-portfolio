"""
Serviço de alertas de preço.

Gerencia criação, listagem, remoção e verificação de alertas.
Multi-tenancy: toda operação filtra por user_id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.concurrency import gather_limited
from app.repositories.brapi.client import BrapiClient
from app.repositories.local.models import AlertModel, get_session


class AlertService:
    """Serviço de gerenciamento de alertas de preço."""

    def __init__(self, brapi_client: BrapiClient) -> None:
        self._brapi = brapi_client

    async def list_alerts(self, user_id: str) -> list[dict[str, Any]]:
        """Lista todos os alertas do usuário."""

        async with get_session() as session:
            result = await session.execute(
                select(AlertModel)
                .where(AlertModel.user_id == user_id)
                .order_by(AlertModel.created_at.desc())
            )
            alerts = result.scalars().all()
            return [
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "target_price": a.target_price,
                    "direction": a.direction,
                    "triggered": a.triggered,
                    "triggered_at": a.triggered_at.isoformat()
                    if a.triggered_at
                    else None,
                    "created_at": a.created_at.isoformat(),
                }
                for a in alerts
            ]

    async def create_alert(
        self, user_id: str, ticker: str, target_price: float, direction: str
    ) -> dict[str, Any]:
        """Cria um novo alerta de preço."""

        async with get_session() as session:
            alert = AlertModel(
                user_id=user_id,
                ticker=ticker.upper(),
                target_price=target_price,
                direction=direction,
            )
            session.add(alert)
            await session.commit()
            await session.refresh(alert)
            return {
                "id": alert.id,
                "ticker": alert.ticker,
                "target_price": alert.target_price,
                "direction": alert.direction,
                "triggered": alert.triggered,
                "triggered_at": None,
                "created_at": alert.created_at.isoformat(),
            }

    async def delete_alert(self, user_id: str, alert_id: str) -> bool:
        """Remove um alerta."""

        async with get_session() as session:
            result = await session.execute(
                select(AlertModel).where(
                    AlertModel.id == alert_id, AlertModel.user_id == user_id
                )
            )
            alert = result.scalars().first()
            if not alert:
                return False
            await session.delete(alert)
            await session.commit()
            return True

    async def check_alert(self, user_id: str, alert_id: str) -> dict[str, Any] | None:
        """Verifica se um alerta específico foi disparado."""

        async with get_session() as session:
            result = await session.execute(
                select(AlertModel).where(
                    AlertModel.id == alert_id, AlertModel.user_id == user_id
                )
            )
            alert = result.scalars().first()
        if not alert:
            return None

        # Busca cotação atual (fora da sync thread, pode usar await)
        raw = await self._brapi.quote(alert.ticker)
        current_price = raw.get("results", [{}])[0].get("regularMarketPrice")

        if current_price is None:
            return {
                "id": alert.id,
                "ticker": alert.ticker,
                "target_price": alert.target_price,
                "direction": alert.direction,
                "current_price": None,
                "triggered": alert.triggered,
                "message": "Não foi possível obter o preço atual",
            }

        # Verifica condição de disparo
        should_trigger = False
        if (alert.direction == "above" and current_price >= alert.target_price) or (
            alert.direction == "below" and current_price <= alert.target_price
        ):
            should_trigger = True

        if should_trigger and not alert.triggered:
            async with get_session() as session:
                result = await session.execute(
                    select(AlertModel).where(AlertModel.id == alert_id)
                )
                a = result.scalars().first()
                if a:
                    a.triggered = True
                    a.triggered_at = datetime.now(UTC)
                    await session.commit()

            return {
                "id": alert.id,
                "ticker": alert.ticker,
                "target_price": alert.target_price,
                "direction": alert.direction,
                "current_price": current_price,
                "triggered": True,
                "message": (
                    f"🔔 Alerta disparado! {alert.ticker} está "
                    f"R$ {current_price} (alvo: R$ {alert.target_price})"
                ),
            }

        return {
            "id": alert.id,
            "ticker": alert.ticker,
            "target_price": alert.target_price,
            "direction": alert.direction,
            "current_price": current_price,
            "triggered": alert.triggered,
            "message": (
                f"{alert.ticker}: R$ {current_price} — "
                f"alvo R$ {alert.target_price} ainda não atingido"
            ),
        }

    async def check_all_alerts(self, user_id: str) -> list[dict[str, Any]]:
        """Verifica todos os alertas não disparados do usuário."""

        async with get_session() as session:
            result = await session.execute(
                select(AlertModel).where(
                    AlertModel.user_id == user_id,
                    AlertModel.triggered.is_(False),
                )
            )
            alerts = result.scalars().all()

        checked = await gather_limited(
            *(self.check_alert(user_id, alert.id) for alert in alerts)
        )
        return [c for c in checked if c is not None]
