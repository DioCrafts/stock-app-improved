"""Endpoints de estados financieros → pantalla Financials.

    GET /companies/{ticker}/financials   (income / balance / cashflow, anuales)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from app.models.financials import FinancialsBundle
from app.services import financials_service
from app.validation import TICKER_PATTERN

router = APIRouter(prefix="/companies", tags=["financials"])


@router.get("/{ticker}/financials", response_model=FinancialsBundle)
def get_financials(ticker: str = Path(pattern=TICKER_PATTERN)) -> FinancialsBundle:
    try:
        return financials_service.build_financials(ticker.upper())
    except Exception as err:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"Sin estados financieros para {ticker}") from err
