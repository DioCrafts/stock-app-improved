"""Métricas de insiders (ventanas, cluster, importes $M) — deterministas, sin red."""
from datetime import date

from app.services.insider_metrics import summarize, to_models

AS_OF = date(2024, 6, 1)

# Solo P/S cuentan; las grant/exercise deben ignorarse en los agregados.
TXNS = [
    {"txn_date": "2024-05-15", "code": "P", "shares": 100000, "price": 180.0, "filer": "Alice"},
    {"txn_date": "2024-05-20", "code": "S", "shares": 50000, "price": 200.0, "filer": "Bob"},
    {"txn_date": "2024-04-01", "code": "P", "shares": 20000, "price": 150.0, "filer": "Carol"},
    {"txn_date": "2024-05-10", "code": "A", "shares": 999999, "price": 0.0, "filer": "Dave"},  # grant → ruido
    {"txn_date": "2023-01-01", "code": "P", "shares": 5000, "price": 10.0, "filer": "Eve"},    # >365d
]


def _win(windows, days):
    return next(w for w in windows if w.days == days)


def test_window_30d_open_market_only():
    w = _win(summarize(TXNS, as_of=AS_OF), 30)   # cutoff 2024-05-02
    assert w.buys == 1 and w.sells == 1           # Alice (P) + Bob (S); grant ignorado
    assert w.buyShares == 100000 and w.sellShares == 50000
    assert w.buyValue == 18.0                      # 100000×180 / 1e6
    assert w.sellValue == 10.0                     # 50000×200 / 1e6
    assert w.netValue == 8.0
    assert w.uniqueBuyers == 1 and w.cluster is False


def test_window_90d_detects_cluster():
    w = _win(summarize(TXNS, as_of=AS_OF), 90)    # cutoff ~2024-03-03 → entra Carol
    assert w.buys == 2 and w.sells == 1
    assert w.buyValue == 21.0                      # 18.0 + (20000×150/1e6 = 3.0)
    assert w.netValue == 11.0
    assert w.uniqueBuyers == 2 and w.cluster is True   # 2 compradores distintos


def test_window_365d_excludes_older():
    w = _win(summarize(TXNS, as_of=AS_OF), 365)   # 2023-01-01 queda fuera (>365d)
    assert w.buys == 2                             # Alice + Carol, NO Eve
    assert w.uniqueBuyers == 2


def test_missing_price_leaves_value_none():
    txns = [{"txn_date": "2024-05-15", "code": "P", "shares": 100, "price": None, "filer": "X"}]
    w = _win(summarize(txns, as_of=AS_OF), 30)
    assert w.buys == 1 and w.buyShares == 100
    assert w.buyValue is None and w.netValue is None   # sin precio → importe desconocido


def test_to_models_sorted_and_value():
    models = to_models(TXNS)
    assert [m.date for m in models[:3]] == ["2024-05-20", "2024-05-15", "2024-05-10"]  # newest-first
    alice = next(m for m in models if m.filer == "Alice")
    assert alice.action == "buy" and alice.value == 18.0
