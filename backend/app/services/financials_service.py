"""Estados financieros → pantalla Financials.

Orquesta yfinance (income/balance/cashflow) + mappers → FinancialsBundle.
Se sirve en vivo (con caché); `currency` = financialCurrency.
"""
from __future__ import annotations

from app.ingest import mappers
from app.ingest import yfinance_client as yfc
from app.models.financials import FinancialsBundle


def build_financials(symbol: str) -> FinancialsBundle:
    income = yfc.get_income_stmt(symbol)
    balance = yfc.get_balance_sheet(symbol)
    cashflow = yfc.get_cashflow(symbol)
    try:
        info = yfc.get_info(symbol)
        currency = info.get("financialCurrency") or info.get("currency")
    except Exception:  # noqa: BLE001
        currency = None
    return mappers.build_financials(symbol, income, balance, cashflow, currency)
