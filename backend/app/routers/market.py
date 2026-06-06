"""Endpoints de mercado → IndexChip + estado "Market open" (cabecera).

    GET /market/indices   (S&P 500 ^GSPC, NASDAQ ^IXIC, VIX ^VIX)
    GET /market/status    (abierto / cerrado)
"""
from __future__ import annotations

from fastapi import APIRouter

from app.models.market import IndexQuote, MarketStatus
from app.services import market_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/indices", response_model=list[IndexQuote])
def indices() -> list[IndexQuote]:
    return market_service.build_indices()


@router.get("/status", response_model=MarketStatus)
def status() -> MarketStatus:
    return market_service.build_market_status()
