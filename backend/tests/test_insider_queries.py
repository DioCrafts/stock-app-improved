"""Persistencia de insiders + filtro del screener (SQLite en memoria, sin red)."""
import json

from app.db import queries
from app.db.schema import connect, init_db
from app.jobs.refresh_snapshots import company_to_row
from app.models.company import Company


def _txn(symbol="AAPL", accession="acc1", code="P", shares=500.0, price=180.0,
         txn_date="2024-05-01", is_derivative=0, source="edgar"):
    return {
        "symbol": symbol, "cik": "0000320193", "accession": accession,
        "filer": "COOK TIMOTHY D", "relationship": "Officer (CEO)", "txn_date": txn_date,
        "code": code, "action": "buy" if code == "P" else "sell", "shares": shares,
        "price": price, "shares_after": 1000.0, "ownership": "D",
        "is_derivative": is_derivative, "source": source, "url": None,
    }


def _conn():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_upsert_dedup():
    conn = _conn()
    assert queries.upsert_insider_transactions(conn, [_txn()]) == 1
    # misma línea (mismo UNIQUE) → no se inserta de nuevo, ni siquiera con otra fuente
    assert queries.upsert_insider_transactions(conn, [_txn(source="dera")]) == 0
    # distinta fecha → fila nueva
    assert queries.upsert_insider_transactions(conn, [_txn(txn_date="2024-05-02")]) == 1
    rows = queries.insider_transactions_for(conn, "AAPL")
    assert len(rows) == 2
    assert rows[0]["txn_date"] == "2024-05-02"   # ORDER BY txn_date DESC


def test_summary_roundtrip():
    conn = _conn()
    row = {
        "symbol": "AAPL", "buys_6m": 3, "sells_6m": 1, "net_value_6m": 8.0,
        "last_txn_date": "2024-05-02", "data": json.dumps([{"days": 180, "buys": 3}]),
    }
    queries.upsert_insider_summary(conn, row)
    got = queries.get_insider_summary(conn, "AAPL")
    assert got["buys_6m"] == 3 and got["net_value_6m"] == 8.0
    assert json.loads(got["data"])[0]["days"] == 180
    assert queries.get_insider_summary(conn, "ZZZZ") is None


def _seed_snapshot(conn, ticker, market="US"):
    c = Company(ticker=ticker, name=f"{ticker} Inc.", sector="Tech", exchange="NMS",
                currency="USD", price=180.0, change=1.0, prevClose=178.0, marketCap=2800.0)
    queries.upsert_snapshots(conn, [company_to_row(c, market)])


def test_screen_insider_filter_and_sort():
    conn = _conn()
    _seed_snapshot(conn, "AAPL")
    _seed_snapshot(conn, "MSFT")
    queries.upsert_insider_summary(conn, {"symbol": "AAPL", "buys_6m": 4, "sells_6m": 0,
                                          "net_value_6m": 8.0, "last_txn_date": "2024-05-02",
                                          "data": "[]"})
    queries.upsert_insider_summary(conn, {"symbol": "MSFT", "buys_6m": 1, "sells_6m": 2,
                                          "net_value_6m": -3.0, "last_txn_date": "2024-05-01",
                                          "data": "[]"})

    # filtro: compra neta 6m ≥ 5 $M → solo AAPL (MSFT es negativo)
    total, blobs = queries.screen(conn, {"insiderNetMin": 5.0}, sort="insider")
    assert total == 1 and '"ticker":"AAPL"' in blobs[0]

    # nº de compras ≥ 2 → solo AAPL
    total, _ = queries.screen(conn, {"insiderBuysMin": 2}, sort="insider")
    assert total == 1

    # orden por insider desc → AAPL (8.0) antes que MSFT (-3.0)
    total, blobs = queries.screen(conn, {}, sort="insider", order="desc")
    assert total == 2 and '"ticker":"AAPL"' in blobs[0]

    # sin filtro de insiders ni sort insider → no se hace JOIN (no excluye por resumen)
    total, _ = queries.screen(conn, {}, sort="price")
    assert total == 2
