"""
Configuração centralizada via pydantic-settings.

Carrega variáveis de ambiente com suporte a .env, tipagem
e validação na inicialização.
"""

from __future__ import annotations

import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # brapi.dev
    brapi_token: str = ""
    brapi_base_url: str = "https://brapi.dev"

    # Database (driver async: aiosqlite em dev, asyncpg em prod)
    database_url: str = "sqlite+aiosqlite:///./data/financeira.db"

    # Ambiente
    environment: str = "development"
    debug: bool = True

    # Cache
    quote_cache_ttl: int = 900  # 15 minutos

    # Rate limiting (token bucket em memória)
    rate_limit_enabled: bool = True
    rate_limit_auth_per_min: int = 60
    rate_limit_auth_burst: int = 100
    rate_limit_public_per_min: int = 10
    rate_limit_data_per_min: int = 60
    rate_limit_data_burst: int = 100
    rate_limit_expensive_per_min: int = 10
    rate_limit_max_buckets: int = 10000  # teto de chaves vivas no RateLimiter

    # Throttle de saída à brapi (protege a quota do plano free)
    brapi_max_concurrency: int = 4
    brapi_min_interval_sec: float = 0.0

    # Cache quente (background)
    warm_cache_enabled: bool = True
    warm_cache_interval_sec: int = 900  # 15 min
    warm_cache_max_tickers: int = 25  # N/T ≤ 1,7 com T=15min

    # Exclusão de conta (soft delete com janela de recuperação)
    account_deletion_grace_days: int = 30

    # Segurança
    secret_key: str = ""

    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _ensure_secret_key(self) -> Settings:
        """Gera uma secret_key aleatória efêmera fora de produção.

        Evita assinar JWTs com chave vazia/previsível em dev e testes. Em
        produção a chave deve vir do ambiente — `check_production_ready` falha
        se ela continuar vazia.
        """
        if not self.secret_key and not self.is_production:
            self.secret_key = secrets.token_urlsafe(32)
        return self

    def check_production_ready(self) -> None:
        """Valida configurações críticas em produção."""
        if not self.is_production:
            return
        errors: list[str] = []
        if (
            not self.secret_key
            or self.secret_key == "dev-secret-key-change-in-production"
        ):
            errors.append(
                "SECRET_KEY precisa ser definida com um valor seguro em produção"
            )
        if not self.brapi_token:
            errors.append("BRAPI_TOKEN precisa ser configurado")
        if errors:
            raise RuntimeError(
                "Configurações de produção inválidas:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )


settings = Settings()
"""Instância global de configuração."""
