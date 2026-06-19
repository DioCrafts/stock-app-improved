"""Métricas de insiders (puras, sin red ni DB) a partir de transacciones normalizadas.

El valor de producto no está en la transacción cruda sino en lo agregado:
¿están comprando o vendiendo, cuánto, en qué ventana, y de forma coordinada?

- Solo se computan operaciones de MERCADO ABIERTO (códigos P/S); el resto
  (concesiones, ejercicios, retenciones fiscales…) es ruido de compensación.
- `cluster` = ≥2 insiders distintos comprando en la ventana (la señal histórica
  más fuerte).
- Importes en millones de la divisa ($M).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.ingest.insider_mappers import code_to_action
from app.models.insider import InsiderTransaction, InsiderWindow

DEFAULT_WINDOWS = (30, 90, 180, 365)


def _to_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _value_m(shares: float | None, price: float | None) -> float | None:
    """shares × price en MILLONES de la divisa ($M). None si falta algún factor."""
    if shares is None or price is None:
        return None
    return round(shares * price / 1e6, 4)


def to_models(transactions: list[dict]) -> list[InsiderTransaction]:
    """Transacciones normalizadas (dict) → modelos InsiderTransaction (con value en $M),
    ordenadas de más reciente a más antigua."""
    out = [
        InsiderTransaction(
            filer=t.get("filer") or "Unknown",
            relationship=t.get("relationship"),
            date=t.get("txn_date"),
            code=t.get("code"),
            action=t.get("action") or code_to_action(t.get("code")),
            shares=t.get("shares"),
            price=t.get("price"),
            value=_value_m(t.get("shares"), t.get("price")),
            sharesAfter=t.get("shares_after"),
            ownership=t.get("ownership"),
            derivative=bool(t.get("is_derivative")),
            url=t.get("url"),
        )
        for t in transactions
    ]
    out.sort(key=lambda x: x.date or "", reverse=True)
    return out


def summarize(transactions: list[dict], as_of: date | None = None,
              windows: tuple[int, ...] = DEFAULT_WINDOWS) -> list[InsiderWindow]:
    """Agrega compras/ventas de mercado abierto por cada ventana de días."""
    as_of = as_of or date.today()
    # Pre-parsear fechas una vez (solo P/S con fecha válida).
    parsed: list[tuple[date, str, float, float | None, str]] = []
    for t in transactions:
        code = (t.get("code") or "").strip().upper()
        if code not in ("P", "S"):
            continue
        d = _to_date(t.get("txn_date"))
        if d is None or d > as_of:
            continue
        shares = t.get("shares") or 0.0
        parsed.append((d, code, shares, _value_m(shares, t.get("price")), t.get("filer") or "?"))

    out: list[InsiderWindow] = []
    for days in windows:
        cutoff = as_of - timedelta(days=days)
        w = InsiderWindow(days=days)
        buyers: set[str] = set()
        sellers: set[str] = set()
        buy_val = sell_val = 0.0
        buy_has = sell_has = False
        for d, code, shares, val, filer in parsed:
            if d < cutoff:
                continue
            if code == "P":
                w.buys += 1
                w.buyShares += shares
                buyers.add(filer)
                if val is not None:
                    buy_val += val
                    buy_has = True
            else:  # S
                w.sells += 1
                w.sellShares += shares
                sellers.add(filer)
                if val is not None:
                    sell_val += val
                    sell_has = True
        w.buyShares = round(w.buyShares, 2)
        w.sellShares = round(w.sellShares, 2)
        w.buyValue = round(buy_val, 4) if buy_has else None
        w.sellValue = round(sell_val, 4) if sell_has else None
        w.netShares = round(w.buyShares - w.sellShares, 2)
        if buy_has or sell_has:
            w.netValue = round((buy_val if buy_has else 0.0) - (sell_val if sell_has else 0.0), 4)
        w.uniqueBuyers = len(buyers)
        w.uniqueSellers = len(sellers)
        w.cluster = len(buyers) >= 2
        out.append(w)
    return out
