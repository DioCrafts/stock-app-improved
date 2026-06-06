"""Descubrimiento de tickers (US / CA / UK) desde FinanceDatabase.

Fuente base (Fase 0): `FinanceDatabase` (MIT). Usamos `fd.Equities()` → SOLO acciones
(los ETFs/fondos viven en clases aparte: fd.ETFs(), fd.Funds()), filtrando por los
exchanges de US/CA/UK. Los símbolos ya son usables por yfinance.

Limitaciones conocidas (documentadas, a refinar):
- FinanceDatabase es estático (~release 2024-06); overlays oficiales = mejora opcional.
- UK incluye cross-listings extranjeros (símbolos `0xxx.L`, divisas no-GBP); se guardan
  `currency`/`country` para poder filtrarlos más adelante.
"""
from __future__ import annotations

import financedatabase as fd
import pandas as pd

from app.config import settings
from app.universe.normalize import MARKET_BY_EXCHANGE, market_for_exchange, to_yahoo

TARGET_EXCHANGES = list(MARKET_BY_EXCHANGE)


def _clean(value) -> str | None:
    """NaN / vacío → None; resto → str."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


# Marcadores de alta precisión de productos cotizados (ETF/ETP/ETC/ETN) que
# FinanceDatabase cuela como "equity". Evita falsos positivos como "American Vanguard".
_FUND_MARKERS = (" etf", " etc", " etp", " etn", "leverage shares", "graniteshares")


def is_fund_like(name: str | None) -> bool:
    """True si el nombre delata un ETF/ETP/ETC/ETN (no es una acción)."""
    if not name:
        return False
    n = name.lower()
    return any(m in n for m in _FUND_MARKERS)


def is_kept(market: str | None, currency: str | None, name: str | None = None,
            uk_gbp_only: bool = True) -> bool:
    """Regla de alcance: solo acciones. UK solo empresas británicas (GBP), excluyendo
    cross-listings extranjeros (decisión 2026-06-05). US/CA íntegros. Se excluyen
    además los ETF/ETP que FinanceDatabase etiqueta como equity."""
    if is_fund_like(name):
        return False
    if uk_gbp_only and market == "UK" and currency != "GBP":
        return False
    return True


def fetch_universe() -> list[dict]:
    """Devuelve la lista de tickers (solo acciones) de US/CA/UK como dicts listos
    para `db.queries.replace_universe`."""
    df = fd.Equities().select()
    df = df[df["exchange"].isin(TARGET_EXCHANGES)]
    df = df[df["name"].notna()]

    rows: list[dict] = []
    for symbol, r in df.iterrows():
        if not isinstance(symbol, str) or not symbol:
            continue
        exchange = r["exchange"]
        market = market_for_exchange(exchange)
        currency = _clean(r.get("currency"))
        name = _clean(r.get("name"))
        if not is_kept(market, currency, name, settings.uk_gbp_only):
            continue
        rows.append(
            {
                "symbol": to_yahoo(symbol, exchange),
                "name": name,
                "exchange": exchange,
                "market": market,
                "currency": currency,
                "sector": _clean(r.get("sector")),
                "country": _clean(r.get("country")),
                "market_cap": _clean(r.get("market_cap")),
            }
        )
    return rows
