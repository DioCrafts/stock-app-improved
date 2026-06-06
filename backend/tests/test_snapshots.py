"""Tests deterministas (sin red) del mapeo y persistencia de company_snapshot."""
from app.db import queries
from app.db.schema import connect, init_db
from app.jobs.refresh_snapshots import company_to_row
from app.models.company import Company


def _company() -> Company:
    return Company(
        ticker="AAPL", name="Apple Inc.", sector="Technology", exchange="NasdaqGS",
        currency="USD", price=300.0, change=1.0, prevClose=297.0, marketCap=4500.0,
        pe=37.0, peg=2.5, pb=42.0, divYield=0.35, roe=141.5, revGrowth=16.6,
        revenue=[383.3, 391.0, 416.2],
    )


def test_company_to_row():
    row = company_to_row(_company(), "US", status="ok")
    assert row["symbol"] == "AAPL" and row["market"] == "US" and row["status"] == "ok"
    assert row["pe"] == 37.0 and row["div_yield"] == 0.35 and row["market_cap"] == 4500.0
    assert row["score_composite"] is None  # Fase 5
    assert '"ticker":"AAPL"' in row["data"].replace(" ", "")


def test_snapshot_db_roundtrip():
    conn = connect(":memory:")
    init_db(conn)
    queries.upsert_snapshots(conn, [company_to_row(_company(), "US")])
    assert queries.count_snapshots(conn) == 1
    assert queries.count_snapshots(conn, status="ok") == 1
    assert queries.snapshot_symbols(conn) == {"AAPL"}
    got = queries.get_snapshot(conn, "AAPL")
    assert got is not None and got["pe"] == 37.0 and got["status"] == "ok"
    # idempotente
    queries.upsert_snapshots(conn, [company_to_row(_company(), "US")])
    assert queries.count_snapshots(conn) == 1
    conn.close()
