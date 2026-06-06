"""Tests deterministas de conversión de unidades (sin red).

Los valores de entrada replican la salida REAL de yfinance 1.4.1 observada en vivo.
"""
from app.ingest.mappers import info_to_company

AAPL_INFO = {
    "longName": "Apple Inc.", "sector": "Technology", "fullExchangeName": "NasdaqGS",
    "exchange": "NMS", "currency": "USD", "fullTimeEmployees": 166000,
    "currentPrice": 307.34, "previousClose": 311.23, "marketCap": 4514011676672, "beta": 1.086,
    "trailingPE": 37.25, "forwardPE": 31.99, "trailingPegRatio": 2.53, "priceToBook": 42.33,
    "priceToSalesTrailing12Months": 9.99, "enterpriseToEbitda": 28.67, "dividendYield": 0.35,
    "freeCashflow": 101090746368, "returnOnEquity": 1.4147, "grossMargins": 0.47862,
    "operatingMargins": 0.32275, "profitMargins": 0.27152, "revenueGrowth": 0.166,
    "earningsGrowth": 0.218, "debtToEquity": 79.548, "currentRatio": 1.07,
}

HSBA_INFO = {
    "longName": "HSBC Holdings plc", "sector": "Financial Services", "fullExchangeName": "LSE",
    "currency": "GBp", "currentPrice": 1360.8, "previousClose": 1367.0,
    "marketCap": 233352822784, "beta": 0.579, "dividendYield": 4.07, "returnOnEquity": 0.11611,
}


def test_units_usd():
    c = info_to_company("AAPL", AAPL_INFO, revenue=[394.3, 383.3, 391.0, 416.2])
    assert c.ticker == "AAPL"
    assert c.currency == "USD"
    assert round(c.marketCap) == 4514                       # ÷1e9
    assert round(c.change, 2) == round((307.34 / 311.23 - 1) * 100, 2)
    assert c.divYield == 0.35                               # NO ×100
    assert round(c.roe, 1) == 141.5                         # ×100
    assert round(c.grossMargin, 1) == 47.9                  # ×100
    assert round(c.debtEq, 3) == 0.795                      # % → ratio (÷100)
    assert round(c.fcfYield, 2) == round(101090746368 / 4514011676672 * 100, 2)
    assert c.roic is None
    assert c.scores is None
    assert c.revenue[-1] == 416.2


def test_gbp_pence_conversion():
    c = info_to_company("HSBA.L", HSBA_INFO)
    assert c.currency == "GBP"                              # convertido desde GBp
    assert round(c.price, 2) == 13.61                       # peniques ÷100 → £
    assert round(c.prevClose, 2) == 13.67
    assert round(c.marketCap) == 233                        # marketCap ya en £, solo ÷1e9
    assert c.divYield == 4.07


def test_missing_fields_become_none():
    c = info_to_company("XXX", {"currency": "USD", "currentPrice": 10.0, "previousClose": 10.0})
    assert c.pe is None and c.roe is None and c.marketCap is None
    assert c.divYield is None and c.revenue == []
    assert c.change == 0.0
