"""Validación de entradas de la API.

El `ticker` fluye a la URL de yfinance; restringirlo a un patrón estricto evita
manipulación de ruta/query del upstream y caracteres peligrosos (M1).
"""
import re

# Símbolos yfinance: letras, dígitos, punto y guion (las clases US ya se normalizan a '-').
TICKER_PATTERN = r"^[A-Za-z0-9.\-]{1,20}$"
_TICKER_RE = re.compile(TICKER_PATTERN)


def is_valid_ticker(symbol: str) -> bool:
    return bool(_TICKER_RE.match(symbol))
