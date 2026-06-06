"""Tests de los modelos del contrato (Fase 1): defaults, opcionales, serialización."""
from app.models.financials import CashFlowYear, FinancialsBundle, IncomeYear
from app.models.market import IndexQuote, MarketStatus
from app.models.price import PricePoint, PriceSeries


def test_price_series():
    ps = PriceSeries(
        ticker="AAPL", range="3M", currency="USD",
        points=[PricePoint(date="2026-06-01", close=300.0), PricePoint(date="2026-06-02", close=305.5)],
    )
    assert ps.range == "3M"
    assert len(ps.points) == 2
    assert ps.points[-1].close == 305.5
    # defaults
    assert PriceSeries(ticker="X", range="1Y").points == []


def test_financials_bundle_optionals():
    inc = IncomeYear(year=2025, revenue=416.2, netInc=112.0)  # resto None
    assert inc.cogs is None and inc.eps is None
    bundle = FinancialsBundle(
        ticker="AAPL", currency="USD", years=[2022, 2023, 2024, 2025],
        income=[inc], cashflow=[CashFlowYear(year=2025, opCF=120.0, fcf=101.0)],
    )
    assert bundle.years[-1] == 2025
    assert bundle.balance == []  # default
    assert bundle.income[0].revenue == 416.2


def test_market_models():
    q = IndexQuote(symbol="^GSPC", label="S&P 500", value=7383.74, change=-2.64)
    assert q.label == "S&P 500"
    assert MarketStatus(open=True).state is None
    assert MarketStatus(open=False, state="CLOSED").state == "CLOSED"
