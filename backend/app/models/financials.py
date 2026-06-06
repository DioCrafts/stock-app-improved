"""Modelos de estados financieros (income / balance / cashflow, anuales).

→ pantalla Financials. Las claves replican las de `STATEMENTS`/`buildStatements`
en src/screens/ValuationFinancials.jsx para minimizar el remapeo en el front.

Origen yfinance (líneas VERIFICADAS en vivo) y unidades:
- Todos los importes en miles de millones ($B) salvo `eps` (por acción, en divisa).
- income:  Total Revenue · Cost Of Revenue · Gross Profit · Operating Expense ·
           Operating Income · Net Income · Diluted EPS
- balance: Cash And Cash Equivalents · Total Assets · Total Debt ·
           Total Liabilities Net Minority Interest · Stockholders Equity
- cashflow: Operating Cash Flow · Capital Expenditure · Free Cash Flow
- Campos ausentes (p.ej. bancos sin Gross Profit) → None (la UI pinta "—").
- `currency` = financialCurrency (puede diferir de la divisa de cotización).
"""
from __future__ import annotations

from pydantic import BaseModel


class IncomeYear(BaseModel):
    year: int
    revenue: float | None = None      # Total Revenue
    cogs: float | None = None         # Cost Of Revenue
    grossProfit: float | None = None  # Gross Profit
    opex: float | None = None         # Operating Expense
    opInc: float | None = None        # Operating Income
    netInc: float | None = None       # Net Income
    eps: float | None = None          # Diluted EPS (por acción, no $B)


class BalanceYear(BaseModel):
    year: int
    cash: float | None = None         # Cash And Cash Equivalents
    assets: float | None = None       # Total Assets
    debt: float | None = None         # Total Debt
    liab: float | None = None         # Total Liabilities Net Minority Interest
    equity: float | None = None       # Stockholders Equity


class CashFlowYear(BaseModel):
    year: int
    opCF: float | None = None         # Operating Cash Flow
    capex: float | None = None        # Capital Expenditure
    fcf: float | None = None          # Free Cash Flow


class FinancialsBundle(BaseModel):
    ticker: str
    currency: str | None = None       # financialCurrency
    years: list[int] = []             # oldest→newest
    income: list[IncomeYear] = []
    balance: list[BalanceYear] = []
    cashflow: list[CashFlowYear] = []
