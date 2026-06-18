"""
Testes de integração do banco de dados local.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import inspect, text

from app.repositories.local.models import (
    OHLCVModel,
    QuoteModel,
    UserModel,
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


async def test_sqlite_usa_wal() -> None:
    """WAL evita que um escritor colida com uma leitura longa em andamento."""
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA journal_mode"))
        assert result.scalar() == "wal"


async def test_escritas_concorrentes_nao_lancam_database_locked() -> None:
    """Várias sessões escrevendo ao mesmo tempo não devem falhar com lock."""

    async def write(i: int) -> None:
        async with get_session() as session:
            session.add(
                UserModel(
                    name=f"Concorrente {i}",
                    email=f"concorrente_{uuid.uuid4().hex[:8]}_{i}@example.com",
                    password_hash="hash",
                )
            )
            await session.commit()

    await asyncio.gather(*(write(i) for i in range(20)))
