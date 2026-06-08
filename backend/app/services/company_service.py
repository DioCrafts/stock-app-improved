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
    """Construye una `Company` real desde yfinance (info + ingresos + sparkline corto)."""
    info = yfc.get_info(symbol)
    years, revenue = mappers.revenue_and_years(yfc.get_income_stmt(symbol))
    company = mappers.info_to_company(symbol, info, revenue, years)
    company.spark = _spark_series(symbol, info.get("currency"))
    return company


def _spark_series(symbol: str, raw_currency: str | None) -> list[float]:
    """Serie corta (~1 mes) de cierres para el mini-sparkline del Watchlist (campo `spark`).
    Falla en silencio → [] (un sparkline ausente nunca debe romper el build/snapshot)."""
    try:
        df = yfc.get_history(symbol, period="1mo", interval="1d")
        return mappers.history_to_spark(df, raw_currency)
    except Exception:  # noqa: BLE001
        return []


def _apply_fx(company: Company) -> Company:
    """Convierte `revenue` (en financialCurrency) a la divisa de cotización para que
    cuadre con price/marketCap en el DCF y los gráficos (M12). No-op si coinciden o
    si el snapshot aún no tiene financialCurrency (se rellena al re-ingerir)."""
    fc = company.financialCurrency
    if fc and company.currency and fc != company.currency and company.revenue:
        rate = yfc.get_fx_rate(fc, company.currency)
        if rate:
            company.revenue = [round(v * rate, 4) for v in company.revenue]
    return company


def get_company(symbol: str) -> Company:
    """Snapshot si existe (status ok); si no, build en vivo. Aplica FX a revenue."""
    conn = connect(settings.db_path)
    try:
        snap = queries.get_snapshot(conn, symbol)
    finally:
        conn.close()
    if snap and snap.get("status") == "ok" and snap.get("data"):
        company = Company.model_validate_json(snap["data"])
    else:
        company = build_company(symbol)
    return _apply_fx(company)


def get_companies(symbols: list[str]) -> list[Company]:
    """Batch: una sola conexión + una query para los que están en snapshot; fallback
    en vivo solo para los que falten (evita N conexiones/N fetches, M6)."""
    conn = connect(settings.db_path)
    try:
        found = queries.snapshots_by_symbols(conn, symbols)
    finally:
        conn.close()
    out: list[Company] = []
    for s in symbols:
        blob = found.get(s)
        try:
            company = Company.model_validate_json(blob) if blob else build_company(s)
        except Exception:  # noqa: BLE001 — un ticker inválido no rompe la lista
            continue
        out.append(_apply_fx(company))
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
