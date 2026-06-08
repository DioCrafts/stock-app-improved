"""Tests deterministas de conversión de unidades (sin red).

Los valores de entrada replican la salida REAL de yfinance 1.4.1 observada en vivo.
"""
import pandas as pd

from app.ingest.mappers import history_to_spark, info_to_company, revenue_and_years

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


def test_revenue_dedup_by_year():  # L1
    df = pd.DataFrame({
        pd.Timestamp("2025-09-30"): {"Total Revenue": 400e9},
        pd.Timestamp("2025-06-30"): {"Total Revenue": 380e9},  # mismo año 2025 (TTM)
        pd.Timestamp("2024-09-30"): {"Total Revenue": 390e9},
    })
    years, rev = revenue_and_years(df)
    assert years == [2024, 2025]      # un único 2025
    assert rev[-1] == 400.0           # conserva la columna más reciente de 2025


def test_zero_values_not_dropped():  # L2 (0.0 es dato válido, no None)
    c = info_to_company("X", {"currency": "USD", "currentPrice": 10.0, "previousClose": 10.0,
                              "marketCap": 1e9, "freeCashflow": 0.0,
                              "trailingPegRatio": 0.0, "pegRatio": 2.0})
    assert c.fcfYield == 0.0          # FCF nulo → yield 0.0, no None
    assert c.peg == 0.0               # respeta el 0.0 de trailing (no cae a pegRatio por truthiness)


def test_history_to_spark_usd_gbp_and_empty():  # campo `spark` del listado (columna 30d)
    usd = pd.DataFrame({"Close": [10.0, 11.0, 12.5]})
    assert history_to_spark(usd, "USD") == [10.0, 11.0, 12.5]
    gbp = pd.DataFrame({"Close": [1000.0, 1100.0]})   # GBp (peniques) → libras ÷100
    assert history_to_spark(gbp, "GBp") == [10.0, 11.0]
    assert history_to_spark(None, "USD") == []         # sin datos → serie vacía
    assert history_to_spark(pd.DataFrame(), "USD") == []
