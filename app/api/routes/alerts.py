"""
Rotas de alertas de preço.

Todas as rotas exigem autenticação JWT.
O usuário só acessa seus próprios alertas (multi-tenancy).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_current_user
from app.core.validation import normalize_ticker
from app.services.alert_service import AlertService

router = APIRouter(prefix="/me/alerts", tags=["Alertas"])


def get_alert_service(request: Request) -> AlertService:
    return AlertService(brapi_client=request.app.state.brapi_client)


@router.get("", summary="Listar alertas")
async def list_alerts(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Lista todos os alertas de preço do usuário."""
    service = get_alert_service(request)
    alerts = await service.list_alerts(current_user["id"])
    return {"alerts": alerts, "total": len(alerts)}


@router.post("", summary="Criar alerta")
async def create_alert(
    request: Request,
    ticker: str = Query(..., description="Ticker do ativo (ex: PETR4)"),
    target_price: float = Query(..., description="Preço alvo"),
    direction: str = Query(
        "below",
        description=(
            "Direção: 'above' (dispara quando subir acima) "
            "ou 'below' (quando cair abaixo)"
        ),
    ),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Cria um alerta de preço para um ativo."""
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if direction not in ("above", "below"):
        raise HTTPException(
            status_code=400,
            detail="Direção inválida. Use 'above' ou 'below'",
        )
    if target_price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Preço alvo deve ser maior que zero",
        )

    service = get_alert_service(request)
    alert = await service.create_alert(
        current_user["id"], ticker, target_price, direction
    )
    return alert


@router.delete("/{alert_id}", summary="Remover alerta")
async def delete_alert(
    alert_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Remove um alerta de preço."""
    service = get_alert_service(request)
    deleted = await service.delete_alert(current_user["id"], alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return {"detail": "Alerta removido com sucesso"}


@router.get("/{alert_id}/check", summary="Verificar alerta")
async def check_alert(
    alert_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Verifica se um alerta específico foi disparado."""
    service = get_alert_service(request)
    result = await service.check_alert(current_user["id"], alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return result


@router.get("/check-all", summary="Verificar todos os alertas")
async def check_all_alerts(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Verifica todos os alertas pendentes do usuário."""
    service = get_alert_service(request)
    results = await service.check_all_alerts(current_user["id"])
    return {"results": results, "total": len(results)}
