"""
Serviço de alertas de preço.

Gerencia criação, listagem, remoção e verificação de alertas.
Multi-tenancy: toda operação filtra por user_id.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.brapi.client import BrapiClient
from app.repositories.local.models import AlertModel, get_session


class AlertService:
    """Serviço de gerenciamento de alertas de preço."""

    def __init__(self, brapi_client: BrapiClient) -> None:
        self._brapi = brapi_client

    async def list_alerts(self, user_id: str) -> list[dict]:
        """Lista todos os alertas do usuário."""
        with get_session() as session:
            alerts = (
                session.query(AlertModel)
                .filter(AlertModel.user_id == user_id)
                .order_by(AlertModel.created_at.desc())
                .all()
            )
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
    ) -> dict:
        """Cria um novo alerta de preço.

        Args:
            user_id: UUID do usuário.
            ticker: Código do ativo (ex: PETR4).
            target_price: Preço alvo para disparo.
            direction: "above" (dispara quando subir acima) ou "below" (quando cair abaixo).

        Returns:
            Dict com dados do alerta criado.
        """
        with get_session() as session:
            alert = AlertModel(
                user_id=user_id,
                ticker=ticker.upper(),
                target_price=target_price,
                direction=direction,
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
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
        with get_session() as session:
            alert = (
                session.query(AlertModel)
                .filter(
                    AlertModel.id == alert_id, AlertModel.user_id == user_id
                )
                .first()
            )
            if not alert:
                return False
            session.delete(alert)
            session.commit()
            return True

    async def check_alert(self, user_id: str, alert_id: str) -> dict | None:
        """Verifica se um alerta específico foi disparado.

        Compara o preço atual do ativo com o alvo definido.

        Args:
            user_id: UUID do usuário.
            alert_id: UUID do alerta.

        Returns:
            Dict com status do alerta ou None se não encontrado.
        """
        with get_session() as session:
            alert = (
                session.query(AlertModel)
                .filter(
                    AlertModel.id == alert_id, AlertModel.user_id == user_id
                )
                .first()
            )
            if not alert:
                return None

            # Busca cotação atual
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
            if alert.direction == "above" and current_price >= alert.target_price:
                should_trigger = True
            elif alert.direction == "below" and current_price <= alert.target_price:
                should_trigger = True

            if should_trigger and not alert.triggered:
                alert.triggered = True
                alert.triggered_at = datetime.now(timezone.utc)
                session.commit()
                return {
                    "id": alert.id,
                    "ticker": alert.ticker,
                    "target_price": alert.target_price,
                    "direction": alert.direction,
                    "current_price": current_price,
                    "triggered": True,
                    "message": f"🔔 Alerta disparado! {alert.ticker} está R$ {current_price} (alvo: R$ {alert.target_price})",
                }

            return {
                "id": alert.id,
                "ticker": alert.ticker,
                "target_price": alert.target_price,
                "direction": alert.direction,
                "current_price": current_price,
                "triggered": alert.triggered,
                "message": f"{alert.ticker}: R$ {current_price} — alvo R$ {alert.target_price} ainda não atingido",
            }

    async def check_all_alerts(self, user_id: str) -> list[dict]:
        """Verifica todos os alertas não disparados do usuário."""
        with get_session() as session:
            alerts = (
                session.query(AlertModel)
                .filter(
                    AlertModel.user_id == user_id, AlertModel.triggered == False
                )
                .all()
            )

        results = []
        for alert in alerts:
            result = await self.check_alert(user_id, alert.id)
            if result:
                results.append(result)

        return results
