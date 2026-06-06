"""Mercado → IndexChip + estado "Market open" (cabecera).

Sustituye los literales hardcodeados de App.jsx. Origen: yfinance `fast_info` (índices)
y `info.marketState` (estado, best-effort).
"""
from __future__ import annotations

from app.ingest import yfinance_client as yfc
from app.models.market import IndexQuote, MarketStatus

_INDICES = [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ"), ("^VIX", "VIX")]


def build_indices() -> list[IndexQuote]:
    out: list[IndexQuote] = []
    for symbol, label in _INDICES:
        try:
            fi = yfc.get_fast_info(symbol)
            last, prev = fi["lastPrice"], fi["previousClose"]
            change = (last / prev - 1) * 100 if prev else 0.0
            out.append(IndexQuote(symbol=symbol, label=label, value=round(last, 2), change=round(change, 2)))
        except Exception:  # noqa: BLE001 — un índice caído no tumba el resto
            continue
    return out


def build_market_status() -> MarketStatus:
    try:
        state = yfc.get_info("^GSPC").get("marketState")
    except Exception:  # noqa: BLE001
        state = None
    return MarketStatus(open=(state == "REGULAR"), state=state)
