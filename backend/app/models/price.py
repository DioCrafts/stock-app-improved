"""Modelos de serie de precios → AreaChart / Sparkline.

La UI (CompanyOverview) consume `hist` como serie de cierres por rango
(1M/3M/6M/1Y) y deriva el rango 52-wk de la serie 1Y. Origen: `Ticker.history`.

Unidades: `close` en la divisa de cotización. Para UK (GBp) el mapper de Fase 6
convierte peniques → libras (÷100), igual que en `Company`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Range = Literal["1M", "3M", "6M", "1Y"]


class PricePoint(BaseModel):
    date: str  # ISO (YYYY-MM-DD)
    close: float


class PriceSeries(BaseModel):
    ticker: str
    range: Range
    currency: str | None = None
    points: list[PricePoint] = []
