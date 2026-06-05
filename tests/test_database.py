"""
Testes de integração do banco de dados local.
"""

from __future__ import annotations

from app.repositories.local.models import (
    OHLCVModel,
    QuoteModel,
    engine,
    get_session,
)


def test_database_connection() -> None:
    """Verifica se o banco está acessível."""
    with get_session() as session:
        result = session.execute(__import__("sqlalchemy").text("SELECT 1"))
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


def test_tables_exist() -> None:
    """Verifica se as tabelas foram criadas."""
    inspector = __import__("sqlalchemy").inspect(engine)
    tables = inspector.get_table_names()
    assert "assets" in tables
    assert "quotes" in tables
    assert "ohlcv" in tables
    assert "dividends" in tables
