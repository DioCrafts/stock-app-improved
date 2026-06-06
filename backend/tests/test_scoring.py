from app.models.company import Company
from app.services.scoring import company_factors, composite_score, compute_scores


def test_composite_nvda():
    # NVDA en src/data.js: value 38, growth 99, health 92, momentum 95 → 75.65 → 76
    assert composite_score(38, 99, 92, 95) == 76


def test_composite_aapl():
    # AAPL: value 52, growth 48, health 78, momentum 60 → 57.2 → 57
    assert composite_score(52, 48, 78, 60) == 57


def test_company_factors_drops_nonpositive_ratios():
    c = Company(ticker="X", name="X", sector="S", exchange="E", currency="USD",
                price=1.0, change=0.0, prevClose=1.0, pe=-5.0, pb=3.0)
    f = company_factors(c)
    assert f["pe"] is None  # P/E negativo (pérdidas) → ignorado
    assert f["pb"] == 3.0


# --- compute_scores: usar muestras ≥ MIN_PERCENTILE_N (10) ---

def _us(n, **factor_lists):
    """n empresas US; factor_lists: {factor: [valores...]} de longitud n."""
    return [
        {"symbol": f"US{i}", "market": "US",
         "factors": {k: vals[i] for k, vals in factor_lists.items()}}
        for i in range(n)
    ]


def test_growth_ranking_per_market():
    recs = _us(12, revGrowth=[float(i) for i in range(12)])
    s = compute_scores(recs)
    assert s["US11"].growth > s["US0"].growth   # más crecimiento → mayor score
    assert s["US11"].value is None              # sin factores de value
    assert s["US11"].composite is None          # un solo pilar → composite None (M13)


def test_value_inversion_low_ratios_win():
    recs = _us(12, pe=[float(10 + i) for i in range(12)], pb=[float(1 + i) for i in range(12)])
    s = compute_scores(recs)
    assert s["US0"].value > s["US11"].value     # ratios más bajos → más "value"


def test_percentile_ignores_small_groups():
    recs = _us(5, revGrowth=[float(i) for i in range(5)])  # n=5 < 10 → factor ignorado (M14)
    s = compute_scores(recs)
    assert all(v.growth is None for v in s.values())


def test_value_pillar_needs_two_factors():
    recs = _us(12, pe=[float(10 + i) for i in range(12)])  # 1 de 8 factores de value
    s = compute_scores(recs)
    assert all(v.value is None for v in s.values())        # < 2 factores → None (M13)


def test_composite_requires_two_pillars():
    g_only = _us(12, revGrowth=[float(i) for i in range(12)])
    assert compute_scores(g_only)["US11"].composite is None
    both = _us(12, revGrowth=[float(i) for i in range(12)], ret_1y=[i / 100 for i in range(12)])
    s = compute_scores(both)
    assert s["US11"].growth is not None and s["US11"].momentum is not None
    assert s["US11"].composite is not None                 # 2 pilares → composite (M13)


def test_per_market_normalization():
    us = _us(12, pe=[float(10 + i) for i in range(12)], pb=[float(1 + i) for i in range(12)])
    uk = [
        {"symbol": f"UK{i}", "market": "UK", "factors": {"pe": float(100 + i), "pb": float(10 + i)}}
        for i in range(12)
    ]
    s = compute_scores(us + uk)
    assert s["US11"].value < s["US0"].value     # rankeado dentro de US
    assert s["UK11"].value < s["UK0"].value     # rankeado dentro de UK
    assert s["UK0"].value > 50                  # el UK más barato puntúa alto pese a ser caro global
