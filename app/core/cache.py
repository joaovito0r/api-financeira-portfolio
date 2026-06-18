"""
Políticas de cache para diferentes tipos de dado.

Define TTLs e lógica de expiração.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.market_hours import is_market_open


class CachePolicy:
    """Define a política de cache para um tipo de dado.

    Attributes:
        ttl: Tempo de vida em segundos.
        perpetual: Se True, o cache nunca expira.
        market_aware: Se True, usa `off_hours_ttl` quando o pregão está fechado.
        off_hours_ttl: TTL em segundos a usar fora do horário de pregão.
    """

    def __init__(
        self,
        ttl: int = 0,
        perpetual: bool = False,
        market_aware: bool = False,
        off_hours_ttl: int = 0,
    ) -> None:
        self.ttl = ttl
        self.perpetual = perpetual
        self.market_aware = market_aware
        self.off_hours_ttl = off_hours_ttl

    def effective_ttl(self) -> int:
        """TTL efetivo: maior fora do pregão quando market_aware."""
        if self.market_aware and not is_market_open():
            return self.off_hours_ttl or self.ttl
        return self.ttl

    def is_expired(self, cached_at: datetime) -> bool:
        """Verifica se o cache expirou."""
        if self.perpetual:
            return False
        ttl = self.effective_ttl()
        if ttl <= 0:
            return True
        return datetime.now() - cached_at > timedelta(seconds=ttl)


# Políticas pré-definidas
QUOTE_CACHE = CachePolicy(ttl=900, market_aware=True, off_hours_ttl=21600)  # 15min / 6h
OHLCV_CACHE = CachePolicy(perpetual=True)  # ∞
DIVIDEND_CACHE = CachePolicy(perpetual=True)
PROFILE_CACHE = CachePolicy(ttl=86400)  # 24h
BALANCE_SHEET_CACHE = CachePolicy(ttl=604800)  # 7 dias
INDICATOR_CACHE = CachePolicy(ttl=3600)  # 1h
STATISTIC_CACHE = CachePolicy(ttl=3600)  # 1h
ASSET_LIST_CACHE = CachePolicy(ttl=86400)  # 24h — lista de ativos muda raro
