"""
Testes do serviço de relatório.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.services.report_service import ReportService


@pytest.mark.asyncio
async def test_gerado_em_e_timezone_aware() -> None:
    """O timestamp 'gerado_em' deve ser timezone-aware (UTC), consistente
    com os demais datetimes do relatório (que usam datetime.now(timezone.utc)).

    Regressão: antes usava __import__("datetime").datetime.now() (naive/local).
    """
    brapi = AsyncMock()
    brapi.quote = AsyncMock(return_value={"results": [{}]})
    brapi.historical = AsyncMock(return_value={"results": [{}]})
    brapi.dividends = AsyncMock(return_value={"results": [{}]})

    service = ReportService(brapi_client=brapi)
    report = await service.generate_report("PETR4")

    gerado_em = datetime.fromisoformat(report["gerado_em"])
    assert gerado_em.tzinfo is not None, (
        f"'gerado_em' deveria ser timezone-aware, veio naive: {report['gerado_em']!r}"
    )
