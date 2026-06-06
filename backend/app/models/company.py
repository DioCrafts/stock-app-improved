"""Modelos del contrato de compañía — espejo de `src/data.js`.

Los nombres de campo se mantienen en camelCase a propósito para que el JSON
coincida 1:1 con el objeto `company` que hoy consume la UI (sin remapeo en el front).

Unidades (ver ARQUITECTURA-BACKEND.md §1):
- marketCap, revenue en miles de millones ($B)
- change en %, ratios de rentabilidad/crecimiento en puntos porcentuales
- los campos Optional pueden venir None (la UI ya pinta "—")
"""
from __future__ import annotations

from pydantic import BaseModel


class Scores(BaseModel):
    # int o None: una empresa sin datos suficientes en un pilar deja ese score en None
    value: int | None = None
    growth: int | None = None
    health: int | None = None
    momentum: int | None = None
    composite: int | None = None


class Company(BaseModel):
    # Identidad
    ticker: str
    name: str
    sector: str
    exchange: str
    currency: str                       # divisa de cotización (UK ya normalizada GBp→GBP)
    financialCurrency: str | None = None  # divisa de los estados (puede diferir; FX para cuadrar)
    employees: int | None = None
    desc: str | None = None
    # Precio / mercado
    price: float
    change: float
    prevClose: float
    marketCap: float | None = None
    beta: float | None = None
    # Valoración
    pe: float | None = None
    fwdPe: float | None = None
    peg: float | None = None
    pb: float | None = None
    ps: float | None = None
    evEbitda: float | None = None
    divYield: float | None = None
    fcfYield: float | None = None
    # Rentabilidad
    roe: float | None = None
    roic: float | None = None
    grossMargin: float | None = None
    opMargin: float | None = None
    netMargin: float | None = None
    # Crecimiento
    revGrowth: float | None = None
    epsGrowth: float | None = None
    # Salud / balance
    debtEq: float | None = None
    currentRatio: float | None = None
    # Scores (None hasta Fase 5: la metodología de los sub-scores no es determinable)
    scores: Scores | None = None
    # Series (la serie de precios `hist` se sirve aparte en /companies/{ticker}/prices)
    revenue: list[float] = []       # $B, oldest→newest
    revenueYears: list[int] = []    # años correspondientes a `revenue` (mismo orden)


class SearchHit(BaseModel):
    """Resultado ligero de GlobalSearch (⌘K). price/composite None si aún no hay snapshot."""
    ticker: str
    name: str | None = None
    price: float | None = None
    composite: int | None = None
