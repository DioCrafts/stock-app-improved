"""Endpoints de compañías → Watchlist, CompanyOverview, Compare.

    GET /companies?tickers=A,B,C   (Watchlist / Compare)
    GET /companies?limit=&offset=  (lista paginada por market cap)
    GET /companies/{ticker}        (ficha completa)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from app.models.company import Company
from app.services import company_service
from app.validation import TICKER_PATTERN, is_valid_ticker

router = APIRouter(prefix="/companies", tags=["companies"])

_MAX_TICKERS = 50  # cota de fan-out por request (limita amplificación a yfinance, M2)


@router.get("", response_model=list[Company])
def list_companies(
    tickers: str | None = Query(None, description="lista separada por comas"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Company]:
    if tickers:
        symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        symbols = [s for s in symbols if is_valid_ticker(s)][:_MAX_TICKERS]
        return company_service.get_companies(symbols)
    return company_service.list_companies(limit=limit, offset=offset)


@router.get("/{ticker}", response_model=Company)
def get_company(ticker: str = Path(pattern=TICKER_PATTERN)) -> Company:
    try:
        return company_service.get_company(ticker.upper())
    except Exception as err:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"Sin datos para {ticker}") from err
