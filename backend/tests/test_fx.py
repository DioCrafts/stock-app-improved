"""Tests de conversión de divisa (M11/M12), sin red."""
from app.ingest.mappers import convert_financials
from app.models.company import Company
from app.models.financials import BalanceYear, CashFlowYear, FinancialsBundle, IncomeYear
from app.services import company_service as cs


def _co(**kw) -> Company:
    base = dict(ticker="X", name="X", sector="S", exchange="E", currency="GBP",
                price=10.0, change=0.0, prevClose=10.0)
    base.update(kw)
    return Company(**base)


def test_apply_fx_converts_revenue(monkeypatch):
    monkeypatch.setattr(cs.yfc, "get_fx_rate", lambda f, t: 0.8)
    out = cs._apply_fx(_co(financialCurrency="USD", revenue=[100.0, 200.0]))
    assert out.revenue == [80.0, 160.0]


def test_apply_fx_noop_same_currency(monkeypatch):
    called = []
    monkeypatch.setattr(cs.yfc, "get_fx_rate", lambda f, t: called.append(1) or 1.0)
    out = cs._apply_fx(_co(currency="USD", financialCurrency="USD", revenue=[100.0]))
    assert out.revenue == [100.0]
    assert not called  # ni se consulta FX si coinciden


def test_apply_fx_noop_without_financial_currency(monkeypatch):
    monkeypatch.setattr(cs.yfc, "get_fx_rate", lambda f, t: 0.5)
    out = cs._apply_fx(_co(financialCurrency=None, revenue=[100.0]))
    assert out.revenue == [100.0]  # snapshot viejo sin financialCurrency → sin conversión


def test_convert_financials():
    b = FinancialsBundle(
        ticker="X", currency="USD", years=[2025],
        income=[IncomeYear(year=2025, revenue=100.0, eps=5.0)],
        balance=[BalanceYear(year=2025, assets=300.0)],
        cashflow=[CashFlowYear(year=2025, fcf=50.0)],
    )
    out = convert_financials(b, 0.8, "GBP")
    assert out.currency == "GBP"
    assert out.income[0].revenue == 80.0
    assert out.income[0].eps == 4.0       # eps (por acción) también convertido
    assert out.balance[0].assets == 240.0
    assert out.cashflow[0].fcf == 40.0
