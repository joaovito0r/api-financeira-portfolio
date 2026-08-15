"""Retrato fixo de dados da conta demo.

Cada constante aqui é o "estado zero" para o qual `app/core/demo_seed.py`
restaura a conta demo periodicamente. Editar estes valores muda o que
recrutadores veem ao explorar a conta — não afeta usuários reais.
"""

from __future__ import annotations

from typing import Any, TypedDict

DEMO_NAME = "Visitante Demo"


class PositionSeed(TypedDict):
    ticker: str
    quantity: int
    avg_cost: float


class WatchlistItemSeed(TypedDict):
    ticker: str
    notes: str | None


class WatchlistSeed(TypedDict):
    name: str
    items: list[WatchlistItemSeed]


class AlertSeed(TypedDict):
    ticker: str
    target_price: float
    direction: str
    triggered: bool


DEMO_PORTFOLIO: list[PositionSeed] = [
    {"ticker": "PETR4", "quantity": 100, "avg_cost": 32.50},
    {"ticker": "VALE3", "quantity": 50, "avg_cost": 68.90},
    {"ticker": "ITUB4", "quantity": 200, "avg_cost": 28.10},
    {"ticker": "WEGE3", "quantity": 80, "avg_cost": 40.75},
    {"ticker": "BBAS3", "quantity": 150, "avg_cost": 26.30},
]

DEMO_WATCHLISTS: list[WatchlistSeed] = [
    {
        "name": "Blue Chips B3",
        "items": [
            {"ticker": "PETR4", "notes": "Petróleo — acompanhar dividendos"},
            {"ticker": "VALE3", "notes": "Minério de ferro, ciclo de commodities"},
            {"ticker": "ITUB4", "notes": None},
        ],
    },
    {
        "name": "Small caps de olho",
        "items": [
            {"ticker": "MGLU3", "notes": "Aguardando recuperação"},
            {"ticker": "RENT3", "notes": None},
            {"ticker": "LREN3", "notes": "Varejo, sensível a juros"},
        ],
    },
]

DEMO_ALERTS: list[AlertSeed] = [
    {
        "ticker": "PETR4",
        "target_price": 40.00,
        "direction": "above",
        "triggered": False,
    },
    {
        "ticker": "VALE3",
        "target_price": 60.00,
        "direction": "below",
        "triggered": False,
    },
    {
        "ticker": "ITUB4",
        "target_price": 30.00,
        "direction": "above",
        "triggered": True,
    },
]


def demo_seed_snapshot() -> dict[str, Any]:
    """Retorna o retrato completo, para uso em testes/depuração."""
    return {
        "name": DEMO_NAME,
        "portfolio": DEMO_PORTFOLIO,
        "watchlists": DEMO_WATCHLISTS,
        "alerts": DEMO_ALERTS,
    }
