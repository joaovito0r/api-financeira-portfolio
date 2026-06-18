"""
Testes de integração do banco de dados local.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.repositories.local.models import (
    OHLCVModel,
    QuoteModel,
    engine,
    get_session,
)


async def test_database_connection() -> None:
    """Verifica se o banco está acessível."""
    async with get_session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_quote_model() -> None:
    """Verifica criação da tabela quotes."""
    assert QuoteModel.__tablename__ == "quotes"
    assert hasattr(QuoteModel, "ticker")
    assert hasattr(QuoteModel, "price")


def test_ohlcv_model() -> None:
    """Verifica criação da tabela ohlcv."""
    assert OHLCVModel.__tablename__ == "ohlcv"
    assert hasattr(OHLCVModel, "ticker")
    assert hasattr(OHLCVModel, "close")


async def test_tables_exist() -> None:
    """Verifica se as tabelas foram criadas."""
    async with engine.connect() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    assert "assets" in tables
    assert "quotes" in tables
    assert "ohlcv" in tables
    assert "dividends" in tables
