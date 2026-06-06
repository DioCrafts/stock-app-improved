"""Modelos de mercado → IndexChip + estado "Market open" (cabecera).

`IndexQuote` alimenta los chips S&P 500 / NASDAQ / VIX (hoy hardcodeados en
App.jsx). Origen: `Ticker("^GSPC"/"^IXIC"/"^VIX").fast_info` (lastPrice + previousClose).
`MarketStatus` sustituye el literal "Market open".
"""
from __future__ import annotations

from pydantic import BaseModel


class IndexQuote(BaseModel):
    symbol: str   # ^GSPC, ^IXIC, ^VIX
    label: str    # "S&P 500", "NASDAQ", "VIX"
    value: float
    change: float  # % vs cierre anterior


class MarketStatus(BaseModel):
    open: bool
    state: str | None = None  # marketState (REGULAR/CLOSED/PRE/POST) si disponible
