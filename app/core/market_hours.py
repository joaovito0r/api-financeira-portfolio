"""Horário de pregão da B3 (sem feriados nesta versão)."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
MARKET_OPEN = time(10, 0)
MARKET_CLOSE = time(17, 0)


def is_market_open(now: datetime | None = None) -> bool:
    """True se o pregão regular está aberto (seg–sex, 10h–17h BRT).

    Feriados da B3 NÃO são considerados nesta versão (limitação conhecida).
    """
    moment = now or datetime.now(SAO_PAULO)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SAO_PAULO)
    else:
        moment = moment.astimezone(SAO_PAULO)
    if moment.weekday() >= 5:  # 5=sábado, 6=domingo
        return False
    return MARKET_OPEN <= moment.time() < MARKET_CLOSE
