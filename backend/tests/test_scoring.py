from app.models.company import Company
from app.services.scoring import company_factors, composite_score, compute_scores


def test_composite_nvda():
    # NVDA en src/data.js: value 38, growth 99, health 92, momentum 95 → 75.65 → 76
    assert composite_score(38, 99, 92, 95) == 76


def test_composite_aapl():
    # AAPL: value 52, growth 48, health 78, momentum 60 → 57.2 → 57
    assert composite_score(52, 48, 78, 60) == 57


def test_growth_ranking_and_composite_renorm():
    recs = [
        {"symbol": "LOW", "market": "US", "factors": {"revGrowth": 1.0, "epsGrowth": 1.0}},
        {"symbol": "MID", "market": "US", "factors": {"revGrowth": 10.0, "epsGrowth": 10.0}},
        {"symbol": "HIGH", "market": "US", "factors": {"revGrowth": 50.0, "epsGrowth": 50.0}},
    ]
    s = compute_scores(recs)
    assert s["HIGH"].growth > s["MID"].growth > s["LOW"].growth
    # solo el pilar growth presente → composite renormalizado == growth
    assert s["HIGH"].value is None
    assert s["HIGH"].composite == s["HIGH"].growth


def test_value_inversion_low_pe_wins():
    recs = [
        {"symbol": "CHEAP", "market": "US", "factors": {"pe": 5.0}},
        {"symbol": "MID", "market": "US", "factors": {"pe": 20.0}},
        {"symbol": "RICH", "market": "US", "factors": {"pe": 100.0}},
    ]
    s = compute_scores(recs)
    assert s["CHEAP"].value > s["RICH"].value  # menor P/E → más value


def test_per_market_normalization():
    # mercados independientes: el único de cada mercado queda en el centro de su grupo
    recs = [
        {"symbol": "US1", "market": "US", "factors": {"revGrowth": 5.0, "epsGrowth": 5.0}},
        {"symbol": "UK1", "market": "UK", "factors": {"revGrowth": 99.0, "epsGrowth": 99.0}},
    ]
    s = compute_scores(recs)
    assert s["US1"].growth == 50 and s["UK1"].growth == 50  # cada uno solo en su mercado


def test_company_factors_drops_nonpositive_ratios():
    c = Company(ticker="X", name="X", sector="S", exchange="E", currency="USD",
                price=1.0, change=0.0, prevClose=1.0, pe=-5.0, pb=3.0)
    f = company_factors(c)
    assert f["pe"] is None  # P/E negativo (pérdidas) → ignorado
    assert f["pb"] == 3.0
