"""Helpers de data/hora compartilhados."""

from __future__ import annotations

import datetime


def utcnow_naive() -> datetime.datetime:
    """Agora em UTC, sem tzinfo.

    As colunas DateTime do projeto guardam datetimes naive; misturar aware e
    naive numa comparação (`>`/`<`) levanta TypeError. Esta função garante
    que todo timestamp da janela de exclusão de conta seja UTC e naive de
    forma consistente, mesmo vindo de arquivos diferentes (auth_service.py,
    account_purge.py).
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
