"""Tests deterministas (sin red) del mapeo de estados financieros."""
import pandas as pd

from app.ingest.mappers import build_financials

C25 = pd.Timestamp("2025-09-30")
C24 = pd.Timestamp("2024-09-30")

INCOME = pd.DataFrame({
    C25: {"Total Revenue": 416e9, "Net Income": 112e9, "Diluted EPS": 6.5, "Operating Income": 130e9},
    C24: {"Total Revenue": 391e9, "Net Income": 99e9, "Diluted EPS": 5.5, "Operating Income": 114e9},
})
BALANCE = pd.DataFrame({
    C25: {"Total Assets": 365e9, "Stockholders Equity": 57e9, "Cash And Cash Equivalents": 30e9},
    C24: {"Total Assets": 352e9, "Stockholders Equity": 56e9, "Cash And Cash Equivalents": 29e9},
})
CASHFLOW = pd.DataFrame({
    C25: {"Operating Cash Flow": 120e9, "Free Cash Flow": 101e9, "Capital Expenditure": -11e9},
    C24: {"Operating Cash Flow": 118e9, "Free Cash Flow": 99e9, "Capital Expenditure": -10e9},
})


def test_build_financials_full():
    b = build_financials("AAPL", INCOME, BALANCE, CASHFLOW, "USD")
    assert b.years == [2024, 2025]  # oldest→newest
    assert b.currency == "USD"
    assert b.income[-1].revenue == 416.0      # ÷1e9
    assert b.income[-1].eps == 6.5            # por acción, sin ÷1e9
    assert b.income[-1].cogs is None          # línea ausente
    assert b.balance[-1].assets == 365.0
    assert b.cashflow[-1].fcf == 101.0
    assert b.cashflow[-1].capex == -11.0


def test_build_financials_bank_missing_lines():
    # banco: solo Total Revenue + Net Income en income
    income = pd.DataFrame({C25: {"Total Revenue": 66e9, "Net Income": 23e9}})
    b = build_financials("HSBA.L", income, pd.DataFrame(), pd.DataFrame(), "USD")
    assert b.years == [2025]
    assert b.income[0].revenue == 66.0
    assert b.income[0].grossProfit is None and b.income[0].opInc is None
    assert b.balance == [] and b.cashflow == []


def test_build_financials_empty():
    empty = pd.DataFrame()
    b = build_financials("X", empty, empty, empty, None)
    assert b.years == [] and b.income == [] and b.balance == [] and b.cashflow == []
