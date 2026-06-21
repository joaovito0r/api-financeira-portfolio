"""
SQLAlchemy models e gerenciamento do banco de dados.

Define as tabelas e o engine para SQLite (dev) ou PostgreSQL (prod).
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import ConnectionPoolEntry

from app.config import settings


class Base(DeclarativeBase):
    """Base declarativa para os modelos."""


class AssetModel(Base):
    """Tabela de ativos financeiros."""

    __tablename__ = "assets"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )


class QuoteModel(Base):
    """Tabela de cotações (cache local)."""

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    price: Mapped[float] = mapped_column(Float)
    change: Mapped[float] = mapped_column(Float)
    change_percent: Mapped[float] = mapped_column(Float)
    day_high: Mapped[float] = mapped_column(Float)
    day_low: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    open: Mapped[float] = mapped_column(Float)
    previous_close: Mapped[float] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    cached_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )


class OHLCVModel(Base):
    """Tabela de preços históricos."""

    __tablename__ = "ohlcv"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class DividendModel(Base):
    """Tabela de dividendos/proventos."""

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    type: Mapped[str] = mapped_column(String(30))
    reference_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)


class CacheEntryModel(Base):
    """Cache genérico chave→JSON para dados lentos (fundamentos, listas)."""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    policy: Mapped[str] = mapped_column(String(50), default="")
    cached_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )


# ── Usuários ──────────────────────────────────────────


class UserModel(Base):
    """Tabela de usuários."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Relacionamentos
    watchlists: Mapped[list[WatchlistModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[AlertModel]] = relationship(cascade="all, delete-orphan")
    portfolio_positions: Mapped[list[PortfolioPositionModel]] = relationship(
        cascade="all, delete-orphan"
    )


class WatchlistModel(Base):
    """Tabela de watchlists do usuário."""

    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )

    # Relacionamentos
    user: Mapped[UserModel] = relationship(back_populates="watchlists")
    items: Mapped[list[WatchlistItemModel]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItemModel(Base):
    """Tabela de itens de uma watchlist."""

    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    watchlist_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )

    # Relacionamentos
    watchlist: Mapped[WatchlistModel] = relationship(back_populates="items")


class AlertModel(Base):
    """Tabela de alertas de preço do usuário."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20))
    target_price: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(
        String(10)
    )  # "above" = dispara quando subir acima, "below" = quando cair abaixo
    triggered: Mapped[bool] = mapped_column(default=False)
    triggered_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )

    # Relacionamentos
    user: Mapped[UserModel] = relationship(overlaps="alerts")


class PortfolioPositionModel(Base):
    """Tabela de posições da carteira do usuário (ticker/quantidade/custo médio)."""

    __tablename__ = "portfolio_positions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    avg_cost: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )

    # Relacionamentos
    user: Mapped[UserModel] = relationship(overlaps="portfolio_positions")


# ── Engine async ─────────────────────────────────────────

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    # connect_args é específico do driver; aiosqlite repassa "timeout" ao
    # sqlite3.connect() subjacente (busy_timeout em segundos).
    connect_args={"timeout": 30} if _is_sqlite else {},
)
SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # mantém atributos acessíveis após o commit
)

if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(
        dbapi_connection: Any, _connection_record: ConnectionPoolEntry
    ) -> None:
        """WAL: leitores não bloqueiam escritores nem vice-versa.

        SQLite (não Postgres/asyncpg de produção) só permite um escritor por
        vez; o modo de journal padrão (rollback journal) faz um escritor
        colidir com uma leitura longa em andamento. WAL evita esse caso, e
        ``connect_args={"timeout": 30}`` acima cobre o caso restante
        (escritor vs. escritor) fazendo a conexão esperar em vez de falhar
        imediatamente com "database is locked".
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async def init_db() -> None:
    """Cria todas as tabelas no banco (de forma assíncrona)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> AsyncSession:
    """Retorna uma nova sessão assíncrona do banco.

    Uso: ``async with get_session() as session: ...``
    """
    return SessionLocal()
