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

    financial_ccy = None
    quote_ccy = None
    try:
        info = yfc.get_info(symbol)
        financial_ccy = info.get("financialCurrency")
        quote = info.get("currency")
        quote_ccy = "GBP" if quote == "GBp" else quote  # UK cotiza en peniques
    except Exception:  # noqa: BLE001
        pass

    bundle = mappers.build_financials(symbol, income, balance, cashflow, financial_ccy)

    # Convertir a la divisa de cotización si difiere, para que cuadre con price/marketCap (M12)
    if financial_ccy and quote_ccy and financial_ccy != quote_ccy:
        rate = yfc.get_fx_rate(financial_ccy, quote_ccy)
        if rate:
            bundle = mappers.convert_financials(bundle, rate, quote_ccy)
    return bundle
