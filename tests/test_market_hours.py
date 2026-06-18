"""Testes do helper de horário de pregão."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.market_hours import is_market_open

SP = ZoneInfo("America/Sao_Paulo")


def test_pregao_aberto_em_dia_util_meio_dia() -> None:
    assert is_market_open(datetime(2026, 6, 17, 12, 0, tzinfo=SP)) is True


def test_pregao_fechado_de_madrugada() -> None:
    assert is_market_open(datetime(2026, 6, 17, 3, 0, tzinfo=SP)) is False


def test_pregao_fechado_no_fim_de_semana() -> None:
    # 2026-06-20 é sábado
    assert is_market_open(datetime(2026, 6, 20, 12, 0, tzinfo=SP)) is False


def test_pregao_fechado_apos_as_17h() -> None:
    assert is_market_open(datetime(2026, 6, 17, 17, 30, tzinfo=SP)) is False
