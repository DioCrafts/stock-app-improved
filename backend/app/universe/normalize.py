"""Normaliza símbolos de exchange a símbolos yfinance/Yahoo y mapea exchange→mercado.

Hallazgos verificados en vivo contra FinanceDatabase (Fase 0/2):
- Los símbolos de FinanceDatabase YA vienen en formato Yahoo, con sufijo:
  TSX `.TO` · TSXV `.V` · CSE `.CN` · Cboe Canada `.NE` · LSE `.L` · IOB `.IL`.
- US sin sufijo y ya con '-' en clases de acción (p.ej. AAQC-UN), sin puntos.
- Edge case menor: algún CPC TSXV trae '.' antes del sufijo (AAJC.P.V); se valida
  contra yfinance en Fase 3 y se descarta si no resuelve.

Por eso la normalización es deliberadamente mínima (KISS): solo US '.'→'-'.
"""
from __future__ import annotations

# Código de exchange (FinanceDatabase) → mercado contemplado
MARKET_BY_EXCHANGE: dict[str, str] = {
    # US
    "NYQ": "US", "NMS": "US", "NGM": "US", "NCM": "US", "ASE": "US",
    # Canadá
    "TOR": "CA", "VAN": "CA", "CNQ": "CA", "NEO": "CA",
    # Reino Unido
    "LSE": "UK", "IOB": "UK", "AQS": "UK",
}

US_EXCHANGES = frozenset(code for code, mkt in MARKET_BY_EXCHANGE.items() if mkt == "US")


def market_for_exchange(code: str | None) -> str | None:
    """Mercado (US/CA/UK) para un código de exchange, o None si no contemplado."""
    return MARKET_BY_EXCHANGE.get(code) if code else None


def to_yahoo(symbol: str, exchange: str) -> str:
    """Símbolo en formato yfinance. Para US, las clases de acción usan '-' en Yahoo,
    pero FinanceDatabase las trae con '.' o '/' (BRK.B/BRK/A → BRK-B/BRK-A); el resto
    se deja como viene (ya trae el sufijo Yahoo correcto)."""
    if exchange in US_EXCHANGES:
        return symbol.replace(".", "-").replace("/", "-")
    return symbol
