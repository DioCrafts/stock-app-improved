"""Lógica de insiders: sirve el `InsiderSummary` que consume la ficha de empresa.

Estrategia (igual que company_service): si hay datos precalculados en DB (job
`refresh_insiders`) se sirven desde ahí; si no, se construye en vivo desde EDGAR
(fallback acotado + cacheado). La actividad de insiders SEC es SOLO US: para
tickers sin CIK (UK/CA) se devuelve un bundle vacío (la UI pinta "sin datos").
"""
from __future__ import annotations

import json

from app.config import settings
from app.db import queries
from app.db.schema import connect
from app.ingest import edgar_client
from app.models.insider import InsiderSummary, InsiderWindow
from app.services import insider_metrics

_LIVE_MAX_FILINGS = 30  # fallback en caliente más ligero que el job batch (latencia)


def build_summary_row(symbol: str, transactions: list[dict], currency: str = "USD") -> dict:
    """Calcula la fila de `insider_summary` (agregados 6m + JSON de ventanas) para el job."""
    windows = insider_metrics.summarize(transactions)
    by_days = {w.days: w for w in windows}
    w6 = by_days.get(180)
    last = max((t.get("txn_date") for t in transactions if t.get("txn_date")), default=None)
    return {
        "symbol": symbol,
        "buys_6m": w6.buys if w6 else 0,
        "sells_6m": w6.sells if w6 else 0,
        "net_value_6m": w6.netValue if w6 else None,
        "last_txn_date": last,
        "currency": currency,
        "data": json.dumps([w.model_dump() for w in windows]),
    }


def get_insider_summary(ticker: str, tx_limit: int = 80) -> InsiderSummary:
    symbol = ticker.upper()
    conn = connect(settings.db_path)
    try:
        stored = queries.get_insider_summary(conn, symbol)
        rows = queries.insider_transactions_for(conn, symbol, limit=tx_limit) if stored else []
    finally:
        conn.close()

    if stored:
        windows = [InsiderWindow.model_validate(w) for w in json.loads(stored.get("data") or "[]")]
        return InsiderSummary(
            ticker=symbol, currency=stored.get("currency") or "USD", updated=stored.get("updated_at"),
            windows=windows, transactions=insider_metrics.to_models(rows),
        )

    # Fallback en vivo desde EDGAR (acotado + cacheado en el cliente). Si la SEC no
    # responde, se devuelve bundle vacío (el widget es complementario, no debe romper
    # la ficha con un 500).
    try:
        raw = edgar_client.fetch_insider_transactions(symbol, max_filings=_LIVE_MAX_FILINGS)
    except Exception:  # noqa: BLE001 — EDGAR caído/timeout → sin datos
        raw = []
    if not raw:
        return InsiderSummary(ticker=symbol, currency=None, windows=[], transactions=[])
    return InsiderSummary(
        ticker=symbol, cik=raw[0].get("cik"), currency="USD", updated=None,
        windows=insider_metrics.summarize(raw),
        transactions=insider_metrics.to_models(raw)[:tx_limit],
    )
