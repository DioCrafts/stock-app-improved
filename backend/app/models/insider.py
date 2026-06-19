"""Modelos del contrato de actividad de insiders (SEC Form 3/4/5) — solo US.

Los nombres de campo se mantienen en camelCase a propósito para que el JSON
coincida 1:1 con lo que consume la UI (sin remapeo en el front), igual que en
`models/company.py`.

Unidades:
- shares: nº de acciones (unidades)
- price: precio por acción en la divisa de cotización (US → USD)
- value / buyValue / sellValue / netValue: importe en MILLONES de la divisa ($M),
  para que sea legible en la UI igual que el resto de magnitudes grandes.
- los campos Optional pueden venir None (la UI pinta "—").
"""
from __future__ import annotations

from pydantic import BaseModel


class InsiderTransaction(BaseModel):
    """Una operación declarada por un insider (una línea de la Table I/II del Form 4)."""
    filer: str                          # nombre del insider (reporting owner)
    relationship: str | None = None     # "Director", "Officer (CEO)", "10% Owner"…
    date: str | None = None             # fecha de la operación (ISO yyyy-mm-dd)
    code: str | None = None             # código SEC: P,S,A,M,F,G,C,X…
    action: str | None = None           # buy|sell|grant|exercise|gift|tax|conversion|other
    shares: float | None = None
    price: float | None = None          # por acción (divisa de cotización)
    value: float | None = None          # shares × price, en $M
    sharesAfter: float | None = None    # acciones en posesión tras la operación
    ownership: str | None = None        # D (directa) | I (indirecta)
    derivative: bool = False            # True si viene de la tabla de derivados (opciones…)
    url: str | None = None              # enlace al filing en EDGAR


class InsiderWindow(BaseModel):
    """Resumen agregado de una ventana temporal (p. ej. últimos 180 días).

    Solo cuenta operaciones de MERCADO ABIERTO (códigos P = compra, S = venta);
    se excluyen concesiones (A), ejercicios (M), retenciones fiscales (F), etc.,
    que son ruido de compensación y no señal de convicción.
    """
    days: int
    buys: int = 0
    sells: int = 0
    buyShares: float = 0.0
    sellShares: float = 0.0
    buyValue: float | None = None       # $M
    sellValue: float | None = None      # $M
    netShares: float = 0.0
    netValue: float | None = None       # $M (compras − ventas)
    uniqueBuyers: int = 0
    uniqueSellers: int = 0
    cluster: bool = False               # True si ≥2 insiders distintos compraron en la ventana


class InsiderSummary(BaseModel):
    """Bundle que sirve el endpoint /companies/{ticker}/insiders."""
    ticker: str
    cik: str | None = None
    currency: str | None = None         # USD para US
    updated: str | None = None          # ISO datetime del último refresco (None = en vivo)
    windows: list[InsiderWindow] = []   # 30/90/180/365 días
    transactions: list[InsiderTransaction] = []  # recientes, newest-first
