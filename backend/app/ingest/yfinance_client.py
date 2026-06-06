"""Wrapper fino sobre yfinance — ÚNICO punto que importa la librería.

Expone .info / .history / .income_stmt con reintentos y caché TTL, para poder
mockearlo o cambiarlo sin tocar el resto.
"""
from __future__ import annotations

import time
from typing import Callable

import yfinance as yf

from app.cache.store import memoize


def _retry(fn: Callable, attempts: int = 3, base_delay: float = 1.0):
    """Reintenta `fn` ante errores transitorios (rate-limit, red)."""
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as err:  # noqa: BLE001 — se relanza el último
            last_err = err
            if i < attempts - 1:
                time.sleep(base_delay * (i + 1))
    raise last_err  # type: ignore[misc]


def get_info(symbol: str) -> dict:
    return memoize(f"info:{symbol}", lambda: _retry(lambda: yf.Ticker(symbol).info))


def get_income_stmt(symbol: str):
    return memoize(f"income:{symbol}", lambda: _retry(lambda: yf.Ticker(symbol).income_stmt))


def get_balance_sheet(symbol: str):
    return memoize(f"balance:{symbol}", lambda: _retry(lambda: yf.Ticker(symbol).balance_sheet))


def get_cashflow(symbol: str):
    return memoize(f"cashflow:{symbol}", lambda: _retry(lambda: yf.Ticker(symbol).cashflow))


def get_history(symbol: str, period: str = "1y", interval: str = "1d"):
    return memoize(
        f"hist:{symbol}:{period}:{interval}",
        lambda: _retry(lambda: yf.Ticker(symbol).history(period=period, interval=interval)),
    )


def get_fast_info(symbol: str) -> dict:
    """Cotización ligera (lastPrice + previousClose) para índices. TTL corto."""
    def fetch() -> dict:
        fi = yf.Ticker(symbol).fast_info
        return {"lastPrice": float(fi["lastPrice"]), "previousClose": float(fi["previousClose"])}

    return memoize(f"fast:{symbol}", lambda: _retry(fetch), ttl=120)


def get_fx_rate(frm: str | None, to: str | None) -> float | None:
    """Tipo de cambio: unidades de `to` por 1 de `frm` (par Yahoo {frm}{to}=X). TTL 1h.
    Devuelve 1.0 si coinciden y None si no se puede obtener."""
    if not frm or not to or frm == to:
        return 1.0
    pair = f"{frm}{to}=X"
    try:
        return memoize(
            f"fx:{pair}",
            lambda: _retry(lambda: float(yf.Ticker(pair).fast_info["lastPrice"])),
            ttl=3600,
        )
    except Exception:  # noqa: BLE001 — par inexistente / sin dato → sin conversión
        return None
