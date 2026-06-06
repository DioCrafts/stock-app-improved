from app.db import queries
from app.db.schema import connect, init_db
from app.universe.normalize import market_for_exchange, to_yahoo
from app.universe.providers import is_fund_like, is_kept


def test_is_fund_like():
    assert is_fund_like("Leverage Shares 2x Netflix ETC A") is True
    assert is_fund_like("iShares Ethereum Trust ETF") is True
    assert is_fund_like("GraniteShares 3x Short Lloyds") is True
    # acciones reales no se confunden
    assert is_fund_like("American Vanguard Corporation") is False
    assert is_fund_like("Apple Inc.") is False
    assert is_fund_like(None) is False


def test_is_kept_excludes_funds():
    assert is_kept("US", "USD", "iShares Ethereum Trust ETF") is False
    assert is_kept("US", "USD", "Apple Inc.") is True


def test_is_kept_uk_gbp_only():
    # UK: solo GBP
    assert is_kept("UK", "GBP", uk_gbp_only=True) is True
    assert is_kept("UK", "EUR", uk_gbp_only=True) is False
    assert is_kept("UK", None, uk_gbp_only=True) is False
    # US/CA intactos
    assert is_kept("US", "USD", uk_gbp_only=True) is True
    assert is_kept("CA", "CAD", uk_gbp_only=True) is True
    # flag desactivado: UK extranjero se conserva
    assert is_kept("UK", "EUR", uk_gbp_only=False) is True


def test_market_for_exchange():
    assert market_for_exchange("NYQ") == "US"
    assert market_for_exchange("TOR") == "CA"
    assert market_for_exchange("VAN") == "CA"
    assert market_for_exchange("LSE") == "UK"
    assert market_for_exchange("IOB") == "UK"
    assert market_for_exchange("ZZZ") is None
    assert market_for_exchange(None) is None


def test_to_yahoo():
    # US: '.' y '/' -> '-' (clases de acción)
    assert to_yahoo("BRK.B", "NYQ") == "BRK-B"
    assert to_yahoo("BRK/A", "NYQ") == "BRK-A"
    assert to_yahoo("BF/B", "NYQ") == "BF-B"
    assert to_yahoo("AAPL", "NMS") == "AAPL"
    # no-US: intacto (FinanceDatabase ya trae sufijo Yahoo)
    assert to_yahoo("SHOP.TO", "TOR") == "SHOP.TO"
    assert to_yahoo("HSBA.L", "LSE") == "HSBA.L"


def test_universe_db_roundtrip():
    conn = connect(":memory:")
    init_db(conn)
    rows = [
        {"symbol": "AAPL", "name": "Apple", "exchange": "NMS", "market": "US",
         "currency": "USD", "sector": "Tech", "country": "United States", "market_cap": "Mega Cap"},
        {"symbol": "SHOP.TO", "name": "Shopify", "exchange": "TOR", "market": "CA",
         "currency": "CAD", "sector": "Tech", "country": "Canada", "market_cap": "Large Cap"},
        {"symbol": "HSBA.L", "name": "HSBC", "exchange": "LSE", "market": "UK",
         "currency": "GBP", "sector": "Financials", "country": "United Kingdom", "market_cap": "Large Cap"},
    ]
    queries.replace_universe(conn, rows)
    assert queries.count_universe(conn) == 3
    assert queries.counts_by_market(conn) == {"CA": 1, "UK": 1, "US": 1}
    # idempotente: recargar no duplica
    queries.replace_universe(conn, rows)
    assert queries.count_universe(conn) == 3
    conn.close()
