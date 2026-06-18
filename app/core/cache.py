"""
Políticas de cache para diferentes tipos de dado.

Define TTLs e lógica de expiração.
"""

from __future__ import annotations

from datetime import datetime, timedelta


class CachePolicy:
    """Define a política de cache para um tipo de dado.

    Attributes:
        ttl: Tempo de vida em segundos.
        perpetual: Se True, o cache nunca expira.
    """

    def __init__(self, ttl: int = 0, perpetual: bool = False) -> None:
        self.ttl = ttl
        self.perpetual = perpetual

    def is_expired(self, cached_at: datetime) -> bool:
        """Verifica se o cache expirou."""
        if self.perpetual:
            return False
        if self.ttl <= 0:
            return True
        return datetime.now() - cached_at > timedelta(seconds=self.ttl)


# Políticas pré-definidas
QUOTE_CACHE = CachePolicy(ttl=900)  # 15 min
OHLCV_CACHE = CachePolicy(perpetual=True)  # ∞
DIVIDEND_CACHE = CachePolicy(perpetual=True)
PROFILE_CACHE = CachePolicy(ttl=86400)  # 24h
BALANCE_SHEET_CACHE = CachePolicy(ttl=604800)  # 7 dias
INDICATOR_CACHE = CachePolicy(ttl=3600)  # 1h
STATISTIC_CACHE = CachePolicy(ttl=3600)  # 1h
ASSET_LIST_CACHE = CachePolicy(ttl=86400)  # 24h — lista de ativos muda raro
