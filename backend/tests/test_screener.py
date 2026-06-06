"""Tests deterministas (sin red) del screener y la búsqueda sobre el snapshot."""
from app.db import queries
from app.db.schema import connect, init_db
from app.jobs.refresh_snapshots import company_to_row
from app.models.company import Company


def _c(ticker, pe=None, mc=None, div=None) -> Company:
    return Company(
        ticker=ticker, name=f"{ticker} Corp", sector="X", exchange="E", currency="USD",
        price=10.0, change=0.0, prevClose=10.0, marketCap=mc, pe=pe, divYield=div,
    )


def _seed(conn):
    queries.upsert_snapshots(conn, [
        company_to_row(_c("AAA", pe=10.0, mc=500.0, div=3.0), "US"),
        company_to_row(_c("BBB", pe=30.0, mc=2000.0, div=0.0), "US"),
        company_to_row(_c("CCC", pe=None, mc=50.0, div=1.0), "UK"),
    ])


def _syms(blobs):
    return [Company.model_validate_json(b).ticker for b in blobs]


def test_screen_pe_filter_excludes_high_and_null():
    conn = connect(":memory:"); init_db(conn); _seed(conn)
    total, blobs = queries.screen(conn, {"peMax": 20.0}, sort="pe", order="asc")
    assert total == 1 and _syms(blobs) == ["AAA"]  # BBB(30) y CCC(null) fuera
    conn.close()


def test_screen_capmin_sorted_desc():
    conn = connect(":memory:"); init_db(conn); _seed(conn)
    _, blobs = queries.screen(conn, {"capMin": 100.0}, sort="marketCap", order="desc")
    assert _syms(blobs) == ["BBB", "AAA"]  # CCC(50) fuera
    conn.close()


def test_screen_score_filter_empty_until_phase5():
    conn = connect(":memory:"); init_db(conn); _seed(conn)
    total, _ = queries.screen(conn, {"valueMin": 50})
    assert total == 0  # scores NULL hasta Fase 5
    conn.close()


def test_search_universe_join():
    conn = connect(":memory:"); init_db(conn)
    queries.replace_universe(conn, [{
        "symbol": "AAPL", "name": "Apple Inc", "exchange": "NMS", "market": "US",
        "currency": "USD", "sector": "Tech", "country": "US", "market_cap": None,
    }])
    queries.upsert_snapshots(conn, [company_to_row(_c("AAPL", pe=37.0, mc=4500.0), "US")])
    hits = queries.search_universe(conn, "app", 10)
    assert hits and hits[0]["symbol"] == "AAPL" and hits[0]["price"] == 10.0
    conn.close()
