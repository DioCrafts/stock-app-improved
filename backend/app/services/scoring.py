"""Cálculo de scores (Fase 5) — metodología aprobada 2026-06-06.

Scoring por **percentiles** dentro de cada **mercado** (US/CA/UK por separado):
cada factor se convierte en su percentil (0–100); los factores "menor es mejor"
se invierten. Cada pilar = media de los percentiles de sus factores disponibles
(si falta un dato, se omite). El composite es la mezcla ponderada de los pilares.

`composite` ES determinable desde data.js:48 (pesos 0.35/0.30/0.20/0.15).
Los pilares value/growth/health/momentum NO eran determinables → esta es la
metodología definida.
"""
from __future__ import annotations

import bisect
import math
from collections import defaultdict

from app.models.company import Company, Scores

W_VALUE, W_GROWTH, W_HEALTH, W_MOMENTUM = 0.35, 0.30, 0.20, 0.15

MIN_PERCENTILE_N = 10       # n mínimo por (mercado, factor) para fiarse del percentil (M14)
MIN_COMPOSITE_PILLARS = 2   # pilares no nulos mínimos para emitir composite (M13)

# (factor, dirección): dir=1 → mayor es mejor · dir=-1 → menor es mejor (se invierte)
VALUE_FACTORS = [
    ("pe", -1), ("fwdPe", -1), ("pb", -1), ("ps", -1), ("evEbitda", -1),
    ("peg", -1), ("fcfYield", 1), ("divYield", 1),
]
GROWTH_FACTORS = [("revGrowth", 1), ("epsGrowth", 1)]
HEALTH_FACTORS = [("roe", 1), ("netMargin", 1), ("opMargin", 1), ("debtEq", -1), ("currentRatio", 1)]
MOMENTUM_FACTORS = [("ret_1y", 1), ("px_vs_200d", 1)]
_ALL_FACTORS = VALUE_FACTORS + GROWTH_FACTORS + HEALTH_FACTORS + MOMENTUM_FACTORS

# Ratios de valoración no positivos no son significativos (pérdidas) → se ignoran
_NONPOSITIVE_TO_NONE = {"pe", "fwdPe", "pb", "ps", "evEbitda", "peg"}


def _jsround(x: float) -> int:
    """Redondeo estilo JS Math.round (para coincidir con el front)."""
    return math.floor(x + 0.5)


def composite_score(value: float, growth: float, health: float, momentum: float) -> int:
    """Mezcla ponderada con los 4 pilares presentes (pesos de data.js:48)."""
    return _jsround(value * W_VALUE + growth * W_GROWTH + health * W_HEALTH + momentum * W_MOMENTUM)


def company_factors(c: Company, ret_1y: float | None = None,
                    px_vs_200d: float | None = None) -> dict:
    """Extrae los factores de un Company + inputs de momentum del snapshot."""
    f = {
        "pe": c.pe, "fwdPe": c.fwdPe, "pb": c.pb, "ps": c.ps, "evEbitda": c.evEbitda,
        "peg": c.peg, "fcfYield": c.fcfYield, "divYield": c.divYield,
        "revGrowth": c.revGrowth, "epsGrowth": c.epsGrowth,
        "roe": c.roe, "netMargin": c.netMargin, "opMargin": c.opMargin,
        "debtEq": c.debtEq, "currentRatio": c.currentRatio,
        "ret_1y": ret_1y, "px_vs_200d": px_vs_200d,
    }
    for k in _NONPOSITIVE_TO_NONE:
        if f[k] is not None and f[k] <= 0:
            f[k] = None
    return f


def _percentile(sorted_vals: list[float], v: float | None, direction: int) -> float | None:
    n = len(sorted_vals)
    # grupos pequeños → el percentil no es fiable (n=1→50, n=2→25/75): se ignora el factor (M14)
    if v is None or n < MIN_PERCENTILE_N:
        return None
    lo = bisect.bisect_left(sorted_vals, v)
    hi = bisect.bisect_right(sorted_vals, v)
    p = (lo + 0.5 * (hi - lo)) / n * 100  # rango medio (midrank)
    return p if direction == 1 else 100 - p


def _pillar(sorted_by_factor: dict, factors: dict, factor_list: list) -> int | None:
    vals = []
    for name, direction in factor_list:
        p = _percentile(sorted_by_factor.get(name, []), factors.get(name), direction)
        if p is not None:
            vals.append(p)
    # cobertura mínima: pilares anchos (≥3 factores) exigen ≥2; los de 2 factores, ≥1 (M13)
    min_required = 2 if len(factor_list) >= 3 else 1
    return _jsround(sum(vals) / len(vals)) if len(vals) >= min_required else None


def _composite(value, growth, health, momentum) -> int | None:
    present = [(s, w) for s, w in
               [(value, W_VALUE), (growth, W_GROWTH), (health, W_HEALTH), (momentum, W_MOMENTUM)]
               if s is not None]
    if len(present) < MIN_COMPOSITE_PILLARS:  # exigir ≥2 pilares (M13: evita composite de un solo pilar)
        return None
    num = sum(s * w for s, w in present)
    den = sum(w for s, w in present)
    return _jsround(num / den)  # pesos renormalizados sobre los pilares presentes


def compute_scores(records: list[dict]) -> dict[str, Scores]:
    """records: [{'symbol', 'market', 'factors': {...}}] → {symbol: Scores}.
    Percentiles calculados por mercado."""
    by_market: dict = defaultdict(lambda: defaultdict(list))
    for r in records:
        for name, _ in _ALL_FACTORS:
            v = r["factors"].get(name)
            if v is not None:
                by_market[r["market"]][name].append(v)
    for market in by_market:
        for name in by_market[market]:
            by_market[market][name].sort()

    out: dict[str, Scores] = {}
    for r in records:
        sbf = by_market[r["market"]]
        f = r["factors"]
        value = _pillar(sbf, f, VALUE_FACTORS)
        growth = _pillar(sbf, f, GROWTH_FACTORS)
        health = _pillar(sbf, f, HEALTH_FACTORS)
        momentum = _pillar(sbf, f, MOMENTUM_FACTORS)
        out[r["symbol"]] = Scores(
            value=value, growth=growth, health=health, momentum=momentum,
            composite=_composite(value, growth, health, momentum),
        )
    return out
