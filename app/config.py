"""
Configuração centralizada via pydantic-settings.

Carrega variáveis de ambiente com suporte a .env, tipagem
e validação na inicialização.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # brapi.dev
    brapi_token: str = "***"
    brapi_base_url: str = "https://brapi.dev"

    # Database
    database_url: str = "sqlite+pysqlite:///./data/financeira.db"

    # Ambiente
    environment: str = "development"
    debug: bool = True

    # Cache
    quote_cache_ttl: int = 900  # 15 minutos

    # Segurança
    secret_key: str = "dev-secret-key-change-in-production"

    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
"""Instância global de configuração."""
