"""
Testes da configuração de segurança (Settings).

Cobre a geração de secret_key em dev e a validação que falha cedo em produção.
"""

from __future__ import annotations

import pytest

from app.config import Settings


def test_dev_gera_secret_key_aleatoria() -> None:
    """Em ambiente não-produção, uma secret_key vazia vira chave aleatória."""
    settings = Settings(environment="development", secret_key="")
    assert settings.secret_key, "secret_key não deveria ficar vazia em dev"
    assert len(settings.secret_key) >= 32


def test_dev_gera_chaves_distintas_por_instancia() -> None:
    """Cada instância sem secret_key explícita recebe uma chave diferente."""
    a = Settings(environment="development", secret_key="")
    b = Settings(environment="development", secret_key="")
    assert a.secret_key != b.secret_key


def test_secret_key_explicita_e_preservada() -> None:
    """Uma secret_key fornecida não é sobrescrita."""
    settings = Settings(environment="development", secret_key="minha-chave-fixa")
    assert settings.secret_key == "minha-chave-fixa"


def test_producao_falha_sem_secret_key() -> None:
    """check_production_ready deve falhar se a secret_key não for definida."""
    settings = Settings(environment="production", secret_key="", brapi_token="token")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.check_production_ready()


def test_producao_ok_com_config_valida() -> None:
    """Com secret_key e brapi_token válidos, a validação passa."""
    settings = Settings(
        environment="production",
        secret_key="chave-segura-de-producao",
        brapi_token="token",
    )
    settings.check_production_ready()  # não deve levantar
