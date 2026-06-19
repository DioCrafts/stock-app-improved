"""Endpoint de actividad de insiders → widget en CompanyOverview (solo US).

    GET /companies/{ticker}/insiders        (resumen por ventanas + operaciones recientes)

Datos de la SEC (Section 16, Form 3/4/5). Para tickers no-US (UK/CA) devuelve un
bundle vacío con 200 (no es un error: simplemente no hay equivalente SEC).
"""
from __future__ import annotations

from fastapi import APIRouter, Path, Query

from app.models.insider import InsiderSummary
from app.services import insider_service
from app.validation import TICKER_PATTERN

router = APIRouter(prefix="/companies", tags=["insiders"])


@router.get("/{ticker}/insiders", response_model=InsiderSummary)
def get_insiders(
    ticker: str = Path(pattern=TICKER_PATTERN),
    limit: int = Query(80, ge=1, le=200, description="máximo de operaciones recientes"),
) -> InsiderSummary:
    return insider_service.get_insider_summary(ticker.upper(), tx_limit=limit)
