"""Endpoint del screener → pantalla Screener (server-side, paginado).

    GET /screener?peMax=20&divMin=2&sort=composite&order=desc&limit=50&offset=0

Parámetros = FILTER_DEFS del front. Devuelve { total, count, results: [Company] }.
Nota: los filtros de score (valueMin/...) no devuelven nada hasta la Fase 5.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import screener_service

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("")
def screen(
    capMin: float | None = Query(None, description="Market cap ≥ ($B)"),
    peMax: float | None = Query(None, description="P/E ≤"),
    pegMax: float | None = Query(None, description="PEG ≤"),
    pbMax: float | None = Query(None, description="P/B ≤"),
    divMin: float | None = Query(None, description="Div yield ≥ (%)"),
    roeMin: float | None = Query(None, description="ROE ≥ (%)"),
    growthRevMin: float | None = Query(None, description="Rev growth ≥ (%)"),
    valueMin: int | None = Query(None, description="Value score ≥"),
    growthMin: int | None = Query(None, description="Growth score ≥"),
    healthMin: int | None = Query(None, description="Health score ≥"),
    momentumMin: int | None = Query(None, description="Momentum score ≥"),
    insiderNetMin: float | None = Query(None, description="Compra neta insiders 6m ≥ ($M, solo US)"),
    insiderBuysMin: int | None = Query(None, description="Nº de compras de insiders 6m ≥ (solo US)"),
    sort: str = Query("composite"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    filters = {
        "capMin": capMin, "peMax": peMax, "pegMax": pegMax, "pbMax": pbMax,
        "divMin": divMin, "roeMin": roeMin, "growthRevMin": growthRevMin,
        "valueMin": valueMin, "growthMin": growthMin, "healthMin": healthMin,
        "momentumMin": momentumMin,
        "insiderNetMin": insiderNetMin, "insiderBuysMin": insiderBuysMin,
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    return screener_service.screen(filters, sort, order, limit, offset)
