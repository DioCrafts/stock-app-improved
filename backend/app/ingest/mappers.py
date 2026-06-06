"""Convierte la salida cruda de yfinance a los modelos Pydantic del contrato.

Conversiones de unidad VERIFICADAS contra yfinance 1.4.1 en vivo (Fase 3):
- marketCap / freeCashflow / revenue → miles de millones ($B)   (÷ 1e9)
- returnOnEquity / *Margins / revenueGrowth / earningsGrowth → puntos % (× 100)
- debtToEquity viene en PORCENTAJE (AAPL 79.5) → ratio (÷ 100) como en data.js
- dividendYield YA viene en puntos % (AAPL 0.35) → NO se multiplica
- change = (price / prevClose - 1) * 100
- UK (currency == "GBp"): price/prevClose en peniques → ÷ 100 a libras;
  marketCap ya viene en GBP (libras), así que NO se divide por 100.
- campos ausentes / NaN → None (la UI ya pinta "—")
- roic: no hay campo directo en yfinance → None (no determinable)
"""
from __future__ import annotations

import math

from app.models.company import Company
from app.models.financials import BalanceYear, CashFlowYear, FinancialsBundle, IncomeYear
from app.models.price import PricePoint, PriceSeries


def _num(v) -> float | None:
    """A float, o None si es None / bool / NaN / no numérico."""
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return None if math.isnan(f) else f


def _int(v) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None


def _pct(v) -> float | None:
    """Fracción (0.47) → puntos porcentuales (47.0)."""
    n = _num(v)
    return n * 100 if n is not None else None


def revenue_and_years(df) -> tuple[list[int], list[float]]:
    """(años, ingresos $B) ordenados oldest→newest. yfinance da columnas newest-first
    y suele traer el periodo más antiguo en NaN."""
    try:
        if df is None or getattr(df, "empty", True) or "Total Revenue" not in df.index:
            return [], []
        series = df.loc["Total Revenue"].dropna()
        pairs = [
            (getattr(ts, "year", None), float(v))
            for ts, v in zip(series.index, series.values)
            if getattr(ts, "year", None) is not None
        ]
        pairs.reverse()  # oldest→newest
        return [y for y, _ in pairs], [v / 1e9 for _, v in pairs]
    except Exception:  # noqa: BLE001 — datos irregulares → series vacías
        return [], []


def info_to_company(symbol: str, info: dict | None, revenue: list[float] | None = None,
                    revenue_years: list[int] | None = None) -> Company:
    info = info or {}
    currency = info.get("currency")

    price = _num(info.get("currentPrice"))
    if price is None:
        price = _num(info.get("regularMarketPrice"))
    prev = _num(info.get("previousClose"))
    if prev is None:
        prev = _num(info.get("regularMarketPreviousClose"))

    # UK en peniques → libras (marketCap ya viene en libras)
    if currency == "GBp":
        if price is not None:
            price /= 100
        if prev is not None:
            prev /= 100
        currency = "GBP"

    if price and prev:
        change = (price / prev - 1) * 100
    else:
        change = _num(info.get("regularMarketChangePercent"))

    mc_abs = _num(info.get("marketCap"))
    fcf = _num(info.get("freeCashflow"))
    debt_eq = _num(info.get("debtToEquity"))

    return Company(
        ticker=symbol,
        name=info.get("longName") or info.get("shortName") or symbol,
        sector=info.get("sector") or "—",
        exchange=info.get("fullExchangeName") or info.get("exchange") or "—",
        currency=currency or "—",
        financialCurrency=info.get("financialCurrency"),
        employees=_int(info.get("fullTimeEmployees")),
        desc=info.get("longBusinessSummary"),
        price=price if price is not None else 0.0,
        change=change if change is not None else 0.0,
        prevClose=prev if prev is not None else 0.0,
        marketCap=(mc_abs / 1e9) if mc_abs is not None else None,
        beta=_num(info.get("beta")),
        pe=_num(info.get("trailingPE")),
        fwdPe=_num(info.get("forwardPE")),
        peg=_num(info.get("trailingPegRatio")) or _num(info.get("pegRatio")),
        pb=_num(info.get("priceToBook")),
        ps=_num(info.get("priceToSalesTrailing12Months")),
        evEbitda=_num(info.get("enterpriseToEbitda")),
        divYield=_num(info.get("dividendYield")),  # ya en puntos %
        fcfYield=(fcf / mc_abs * 100) if (fcf and mc_abs) else None,
        roe=_pct(info.get("returnOnEquity")),
        roic=None,  # no determinable desde yfinance
        grossMargin=_pct(info.get("grossMargins")),
        opMargin=_pct(info.get("operatingMargins")),
        netMargin=_pct(info.get("profitMargins")),
        revGrowth=_pct(info.get("revenueGrowth")),
        epsGrowth=_pct(info.get("earningsGrowth")),
        debtEq=(debt_eq / 100) if debt_eq is not None else None,  # % → ratio
        currentRatio=_num(info.get("currentRatio")),
        scores=None,  # Fase 5
        revenue=revenue or [],
        revenueYears=revenue_years or [],
    )


def history_to_price_series(symbol: str, range_: str, df, currency: str | None = None) -> PriceSeries:
    """`Ticker.history` → PriceSeries. UK (GBp): Close en peniques → libras (÷100)."""
    gbp = currency == "GBp"
    out_currency = "GBP" if gbp else currency
    points: list[PricePoint] = []
    try:
        if df is not None and not getattr(df, "empty", True) and "Close" in df.columns:
            for ts, close in df["Close"].items():
                c = _num(close)
                if c is None:
                    continue
                points.append(PricePoint(date=str(ts.date()), close=round(c / 100 if gbp else c, 4)))
    except Exception:  # noqa: BLE001 — datos irregulares → serie vacía
        points = []
    return PriceSeries(ticker=symbol, range=range_, currency=out_currency, points=points)


def _columns_by_year(df) -> dict[int, object]:
    """{año → columna} de un statement. Columnas newest-first → conserva la más reciente por año."""
    out: dict[int, object] = {}
    if df is None or getattr(df, "empty", True):
        return out
    for col in df.columns:
        year = getattr(col, "year", None)
        if year is not None and year not in out:
            out[year] = col
    return out


def _sv(df, label: str, col, scale: float = 1e9) -> float | None:
    """Valor de una línea de statement (label, año) escalado; None si falta o NaN."""
    try:
        if df is None or label not in df.index:
            return None
        v = _num(df.loc[label, col])
        return v / scale if v is not None else None
    except Exception:  # noqa: BLE001
        return None


def build_financials(symbol: str, income_df, balance_df, cashflow_df,
                     currency: str | None = None) -> FinancialsBundle:
    """yfinance (income/balance/cashflow) → FinancialsBundle. Importes ÷1e9 ($B) salvo eps.
    Statements en financialCurrency (NO peniques), así que no se aplica el ÷100 de UK."""
    inc_cols = _columns_by_year(income_df)
    bal_cols = _columns_by_year(balance_df)
    cf_cols = _columns_by_year(cashflow_df)
    years = sorted(set(inc_cols) | set(bal_cols) | set(cf_cols))

    income, balance, cashflow = [], [], []
    for y in years:
        if y in inc_cols:
            col = inc_cols[y]
            income.append(IncomeYear(
                year=y,
                revenue=_sv(income_df, "Total Revenue", col),
                cogs=_sv(income_df, "Cost Of Revenue", col),
                grossProfit=_sv(income_df, "Gross Profit", col),
                opex=_sv(income_df, "Operating Expense", col),
                opInc=_sv(income_df, "Operating Income", col),
                netInc=_sv(income_df, "Net Income", col),
                eps=_sv(income_df, "Diluted EPS", col, scale=1),  # por acción, no $B
            ))
        if y in bal_cols:
            col = bal_cols[y]
            balance.append(BalanceYear(
                year=y,
                cash=_sv(balance_df, "Cash And Cash Equivalents", col),
                assets=_sv(balance_df, "Total Assets", col),
                debt=_sv(balance_df, "Total Debt", col),
                liab=_sv(balance_df, "Total Liabilities Net Minority Interest", col),
                equity=_sv(balance_df, "Stockholders Equity", col),
            ))
        if y in cf_cols:
            col = cf_cols[y]
            cashflow.append(CashFlowYear(
                year=y,
                opCF=_sv(cashflow_df, "Operating Cash Flow", col),
                capex=_sv(cashflow_df, "Capital Expenditure", col),
                fcf=_sv(cashflow_df, "Free Cash Flow", col),
            ))
    return FinancialsBundle(ticker=symbol, currency=currency, years=years,
                            income=income, balance=balance, cashflow=cashflow)


_FX_FIELDS = {
    "income": ("revenue", "cogs", "grossProfit", "opex", "opInc", "netInc", "eps"),
    "balance": ("cash", "assets", "debt", "liab", "equity"),
    "cashflow": ("opCF", "capex", "fcf"),
}


def convert_financials(bundle: FinancialsBundle, rate: float, currency: str) -> FinancialsBundle:
    """Multiplica todos los importes (incl. eps, por acción) por `rate` y fija la divisa
    a `currency`. Para cuadrar los estados con la divisa de cotización (M12)."""
    def conv(records, keys):
        for rec in records:
            for k in keys:
                v = getattr(rec, k)
                if v is not None:
                    setattr(rec, k, round(v * rate, 4))

    conv(bundle.income, _FX_FIELDS["income"])
    conv(bundle.balance, _FX_FIELDS["balance"])
    conv(bundle.cashflow, _FX_FIELDS["cashflow"])
    bundle.currency = currency
    return bundle
