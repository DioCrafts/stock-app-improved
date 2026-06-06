"""Caché TTL en disco (diskcache) para datos on-demand (info / precios / estados
financieros), para no martillear yfinance.
"""
from __future__ import annotations

from typing import Callable

from diskcache import Cache

from app.config import settings

_cache = Cache(settings.cache_dir)
_MISS = object()


def memoize(key: str, producer: Callable, ttl: int | None = None):
    """Devuelve el valor cacheado para `key`; si no existe, lo produce y lo cachea
    con expiración TTL (por defecto `settings.cache_ttl_seconds`)."""
    value = _cache.get(key, default=_MISS)
    if value is not _MISS:
        return value
    value = producer()
    _cache.set(key, value, expire=ttl or settings.cache_ttl_seconds)
    return value
