"""
Validação e normalização de entradas de usuário.

Centraliza a sanitização de tickers antes de usá-los em URLs externas
(brapi.dev) ou persisti-los, evitando injeção na requisição e lixo no cache.
"""

from __future__ import annotations

import re

# Tickers da B3 são alfanuméricos (ex: PETR4, BOVA11, HGLG11). Sem espaços,
# barras, '?' ou outros caracteres que poderiam alterar a URL externa.
_TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}$")


def normalize_ticker(raw: str) -> str:
    """Normaliza e valida um código de ativo.

    Args:
        raw: Ticker fornecido pelo usuário.

    Returns:
        Ticker em maiúsculas e sem espaços nas bordas.

    Raises:
        ValueError: Se o formato for inválido.
    """
    ticker = raw.strip().upper()
    if not _TICKER_RE.fullmatch(ticker):
        raise ValueError(
            f"Ticker inválido: {raw!r}. Use apenas letras e números "
            "(1 a 10 caracteres), ex: PETR4."
        )
    return ticker
