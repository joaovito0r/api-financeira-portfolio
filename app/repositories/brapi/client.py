"""
Cliente HTTP assíncrono para a API brapi.dev.

Adaptado do projeto original do usuário com melhorias:
- Singleton pattern via FastAPI lifespan
- Tratamento robusto de erros
- Suporte a módulos (summaryProfile, financialData, etc.)
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.core.validation import normalize_ticker


class BrapiClient:
    """Cliente para API brapi.dev."""

    BASE_URL = settings.brapi_base_url

    def __init__(self) -> None:
        """Inicializa cliente HTTP com token de autenticação."""
        token = settings.brapi_token
        if not token:
            raise ValueError(
                "BRAPI_TOKEN não configurado. "
                "Defina BRAPI_TOKEN no .env ou adquira um em https://brapi.dev"
            )

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=10.0,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def close(self) -> None:
        """Fecha a sessão HTTP."""
        await self._client.aclose()

    @staticmethod
    def _safe_ticker(ticker: str) -> str:
        """Valida o ticker antes de inseri-lo na URL externa (evita injeção)."""
        try:
            return normalize_ticker(ticker)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    # ── Cotação ──────────────────────────────────────────────

    async def quote(self, ticker: str, modules: str | None = None) -> dict[str, Any]:
        """Cotação de um ativo.

        Args:
            ticker: Código do ativo (ex: PETR4).
            modules: Módulos extras separados por vírgula
                     (summaryProfile, financialData, etc.).

        Returns:
            Dict com os dados da cotação.
        """
        ticker = self._safe_ticker(ticker)
        params: dict[str, str] = {}
        if modules:
            params["modules"] = modules

        return await self._get(f"/api/quote/{ticker}", params=params)

    async def multiple_quote(
        self, tickers: list[str], modules: str | None = None
    ) -> dict[str, Any]:
        """Cotação de múltiplos ativos em uma requisição.

        Args:
            tickers: Lista de códigos (ex: ["PETR4", "VALE3"]).
            modules: Módulos extras.

        Nota: No plano gratuito, apenas 1 ticker por request.
              Múltiplos tickers funcionam apenas nos planos pagos.
        """
        safe = [self._safe_ticker(t) for t in tickers]
        params: dict[str, str] = {"tickers": ",".join(safe)}
        if modules:
            params["modules"] = modules

        return await self._get("/api/quote", params=params)

    async def historical(
        self,
        ticker: str,
        range: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Histórico OHLCV de um ativo.

        Args:
            ticker: Código do ativo.
            range: Período (1d, 5d, 1mo, 6mo, 1y, 5y, max).
            interval: Intervalo (1d, 1wk, 1mo).
        """
        ticker = self._safe_ticker(ticker)
        return await self._get(
            f"/api/quote/{ticker}",
            params={"range": range, "interval": interval},
        )

    async def dividends(self, ticker: str) -> dict[str, Any]:
        """Histórico de dividendos/proventos de um ativo."""
        ticker = self._safe_ticker(ticker)
        return await self._get(
            f"/api/quote/{ticker}",
            params={"dividends": "true"},
        )

    # ── Listagem ─────────────────────────────────────────────

    async def list_assets(
        self, search: str | None = None, sector: str | None = None
    ) -> dict[str, Any]:
        """Lista ativos disponíveis com filtros."""
        params: dict[str, str] = {}
        if search:
            params["search"] = search
        if sector:
            params["sector"] = sector
        return await self._get("/api/quote/list", params=params)

    async def available(self) -> dict[str, Any]:
        """Lista simplificada de ativos disponíveis."""
        return await self._get("/api/available")

    # ── Utilitários ──────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Health check da API brapi.dev."""
        return await self._get("/health")

    async def dictionary(self, search: str | None = None) -> dict[str, Any]:
        """Dicionário de campos da API."""
        params = {}
        if search:
            params["search"] = search
        return await self._get("/api/v2/dictionary", params=params)

    # ── Internos ─────────────────────────────────────────────

    async def _get(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Executa GET request com tratamento de erro."""
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Tempo limite excedido na API brapi.dev",
            ) from None
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Erro na API brapi.dev: {e.response.text}",
            ) from e
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Não foi possível conectar à API brapi.dev",
            ) from None
