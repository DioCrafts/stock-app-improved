"""Lógica de compañías: sirve el `Company` que consume la UI.

Estrategia: si hay snapshot precalculado (Fase 4) se devuelve desde DB; si no, se
construye en vivo desde yfinance (fallback). Prices se sirven siempre en vivo (+ caché).
"""
from __future__ import annotations

from app.config import settings
from app.db import queries
from app.db.schema import connect
from app.ingest import mappers
from app.ingest import yfinance_client as yfc
from app.models.company import Company, SearchHit
from app.models.price import PriceSeries

_RANGE_TO_PERIOD = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}


def build_company(symbol: str) -> Company:
    """Construye una `Company` real desde yfinance (info + ingresos)."""
    info = yfc.get_info(symbol)
    years, revenue = mappers.revenue_and_years(yfc.get_income_stmt(symbol))
    return mappers.info_to_company(symbol, info, revenue, years)


def get_company(symbol: str) -> Company:
    """Snapshot si existe (status ok); si no, build en vivo."""
    conn = connect(settings.db_path)
    try:
        snap = queries.get_snapshot(conn, symbol)
    finally:
        conn.close()
    if snap and snap.get("status") == "ok" and snap.get("data"):
        return Company.model_validate_json(snap["data"])
    return build_company(symbol)


def get_companies(symbols: list[str]) -> list[Company]:
    out: list[Company] = []
    for s in symbols:
        try:
            out.append(get_company(s))
        except Exception:  # noqa: BLE001 — un ticker inválido no rompe la lista
            continue
    return out


def list_companies(limit: int = 50, offset: int = 0) -> list[Company]:
    conn = connect(settings.db_path)
    try:
        blobs = queries.list_company_data(conn, limit, offset)
    finally:
        conn.close()
    return [Company.model_validate_json(b) for b in blobs if b]


def build_price_series(symbol: str, range_: str) -> PriceSeries:
    period = _RANGE_TO_PERIOD.get(range_, "3mo")
    df = yfc.get_history(symbol, period=period, interval="1d")
    try:
        currency = yfc.get_info(symbol).get("currency")
    except Exception:  # noqa: BLE001
        currency = None
    return mappers.history_to_price_series(symbol, range_, df, currency)


def search(q: str, limit: int = 10) -> list[SearchHit]:
    conn = connect(settings.db_path)
    try:
        rows = queries.search_universe(conn, q, limit)
    finally:
        conn.close()
    return [
        SearchHit(ticker=r["symbol"], name=r["name"], price=r["price"], composite=r["score_composite"])
        for r in rows
    ]
