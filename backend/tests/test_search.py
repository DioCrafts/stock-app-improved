"""Tests de búsqueda FTS5 (L7), sin red."""
from app.db import queries
from app.db.schema import connect, init_db

_UNIVERSE = [
    {"symbol": "AAPL", "name": "Apple Inc", "exchange": "NMS", "market": "US",
     "currency": "USD", "sector": "Tech", "country": "US", "market_cap": None},
    {"symbol": "MSFT", "name": "Microsoft Corp", "exchange": "NMS", "market": "US",
     "currency": "USD", "sector": "Tech", "country": "US", "market_cap": None},
]


def _seed():
    conn = connect(":memory:")
    init_db(conn)
    queries.replace_universe(conn, _UNIVERSE)
    queries.rebuild_universe_fts(conn)
    return conn


def test_search_prefix_name():
    conn = _seed()
    syms = [r["symbol"] for r in queries.search_universe(conn, "app", 10)]
    assert "AAPL" in syms and "MSFT" not in syms
    assert "MSFT" in [r["symbol"] for r in queries.search_universe(conn, "micro", 10)]
    conn.close()


def test_search_prefix_ticker():
    conn = _seed()
    assert "AAPL" in [r["symbol"] for r in queries.search_universe(conn, "AAP", 10)]
    conn.close()


def test_search_sanitizes_special_chars():
    conn = _seed()
    # caracteres no alfanuméricos no rompen FTS (se sanean); 'app' sigue casando
    syms = [r["symbol"] for r in queries.search_universe(conn, 'app"*(', 10)]
    assert "AAPL" in syms
    assert queries.search_universe(conn, "!!!", 10) == []  # sin tokens → vacío
    conn.close()
