"""Endpoints de precios → AreaChart / Sparkline.

    GET /companies/{ticker}/prices?range=1M|3M|6M|1Y
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.price import PriceSeries, Range
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["prices"])


@router.get("/{ticker}/prices", response_model=PriceSeries)
def get_prices(ticker: str, range: Range = "3M") -> PriceSeries:
    try:
        return company_service.build_price_series(ticker.upper(), range)
    except Exception as err:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"Sin precios para {ticker}") from err
