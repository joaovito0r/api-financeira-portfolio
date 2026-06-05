"""
Entidade de domínio: Perfil da Empresa (CompanyProfile).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompanyProfile:
    """Dados cadastrais e descritivos de uma empresa.

    Attributes:
        ticker: Código do ativo.
        address: Endereço.
        city: Cidade.
        state: Estado.
        country: País.
        website: Site oficial.
        industry: Setor de atuação.
        sector: Segmento.
        description: Descrição do negócio.
        employees: Número de funcionários.
    """

    ticker: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    website: str | None = None
    industry: str | None = None
    sector: str | None = None
    description: str | None = None
    employees: int | None = None
