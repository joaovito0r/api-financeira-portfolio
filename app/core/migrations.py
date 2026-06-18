"""Aplica migrations do Alembic no startup da aplicação.

`alembic.command.upgrade` é síncrono e roda seu próprio loop assíncrono
internamente (`asyncio.run` dentro de `alembic/env.py`); por isso é
executado em thread separada (`asyncio.to_thread`) para não colidir com o
loop já em execução no lifespan do FastAPI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic.config import Config

from alembic import command

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _upgrade_head() -> None:
    config = Config(str(_ALEMBIC_INI))
    command.upgrade(config, "head")


async def run_migrations() -> None:
    """Aplica todas as migrations pendentes até a revisão `head`."""
    await asyncio.to_thread(_upgrade_head)
