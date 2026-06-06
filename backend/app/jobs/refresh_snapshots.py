"""Job batch: refresca `company_snapshot` para todo el universo desde yfinance.

Diseño para ~14k tickers con rate-limit de Yahoo:
- **Resumible**: por defecto salta los símbolos que ya tienen snapshot (`only_missing`),
  así se puede ejecutar en varias tandas si Yahoo corta.
- **Tolerante a fallos**: un ticker que falla se guarda con `status='error'` (no aborta).
- **Pausas**: `pause` segundos entre tickers + escritura por lotes.

Ejecutar manualmente:
    uv run python -m app.jobs.refresh_snapshots            # todo lo que falte
    uv run python -m app.jobs.refresh_snapshots --limit 50 # solo 50 (smoke test)
    uv run python -m app.jobs.refresh_snapshots --all      # refrescar también los ya hechos
"""
from __future__ import annotations

import time

from app.config import settings
from app.db import queries
from app.db.schema import connect, init_db
from app.ingest import yfinance_client as yfc
from app.ingest.mappers import _num
from app.models.company import Company
from app.services.company_service import build_company

_BATCH_WRITE = 25


def company_to_row(company: Company, market: str | None, status: str = "ok",
                   error: str | None = None, ret_1y: float | None = None,
                   px_vs_200d: float | None = None) -> dict:
    """Mapea un `Company` a una fila de `company_snapshot` (columnas + JSON).
    Los scores se rellenan después en la pasada de scoring (Fase 5)."""
    return {
        "symbol": company.ticker,
        "name": company.name,
        "market": market,
        "sector": company.sector,
        "price": company.price,
        "change": company.change,
        "market_cap": company.marketCap,
        "pe": company.pe,
        "peg": company.peg,
        "pb": company.pb,
        "div_yield": company.divYield,
        "roe": company.roe,
        "rev_growth": company.revGrowth,
        "score_value": None,
        "score_growth": None,
        "score_health": None,
        "score_momentum": None,
        "score_composite": None,
        "ret_1y": ret_1y,
        "px_vs_200d": px_vs_200d,
        "data": company.model_dump_json(),
        "status": status,
        "error": error,
    }


def _error_row(symbol: str, market: str | None, error: str) -> dict:
    return {
        "symbol": symbol, "name": None, "market": market, "sector": None,
        "price": None, "change": None, "market_cap": None, "pe": None, "peg": None,
        "pb": None, "div_yield": None, "roe": None, "rev_growth": None,
        "score_value": None, "score_growth": None, "score_health": None,
        "score_momentum": None, "score_composite": None,
        "ret_1y": None, "px_vs_200d": None,
        "data": None, "status": "error", "error": error[:300],
    }


def build_snapshot_row(symbol: str, market: str | None) -> dict:
    try:
        company = build_company(symbol)
        info = yfc.get_info(symbol)  # cacheado (lo usó build_company)
        ret_1y = _num(info.get("52WeekChange"))
        px = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
        ma200 = _num(info.get("twoHundredDayAverage"))
        px_vs_200d = (px / ma200 - 1) if (px and ma200) else None
        return company_to_row(company, market, ret_1y=ret_1y, px_vs_200d=px_vs_200d)
    except Exception as err:  # noqa: BLE001 — un fallo no debe abortar el lote
        return _error_row(symbol, market, str(err))


def refresh_snapshots(limit: int | None = None, only_missing: bool = True,
                      max_age_hours: float | None = None, pause: float = 0.7,
                      db_path: str | None = None, log_every: int = 50) -> dict:
    """Recorre el universo y persiste snapshots. Devuelve un resumen.

    - `max_age_hours` (refresco): re-procesa lo que falte + lo más viejo que ese umbral.
    - `only_missing` (backfill, por defecto): salta todo lo ya presente (ignorado si hay max_age_hours).
    """
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        universe = queries.universe_rows(conn)
        if max_age_hours is not None:
            done = queries.fresh_symbols(conn, max_age_hours)
        elif only_missing:
            # solo lo que está OK cuenta como "hecho" → los status='error' se reintentan (H1)
            done = queries.snapshot_symbols(conn, status="ok")
        else:
            done = set()
        todo = [u for u in universe if u["symbol"] not in done]
        if limit:
            todo = todo[:limit]

        ok = err = 0
        batch: list[dict] = []
        for i, u in enumerate(todo, 1):
            row = build_snapshot_row(u["symbol"], u["market"])
            batch.append(row)
            ok, err = (ok + 1, err) if row["status"] == "ok" else (ok, err + 1)
            if len(batch) >= _BATCH_WRITE:
                queries.upsert_snapshots(conn, batch)
                batch = []
            if i % log_every == 0:
                print(f"  {i}/{len(todo)} (ok={ok} err={err})", flush=True)
            if pause:
                time.sleep(pause)
        if batch:
            queries.upsert_snapshots(conn, batch)

        return {
            "processed": len(todo),
            "ok": ok,
            "errors": err,
            "snapshots_total": queries.count_snapshots(conn),
            "universe_total": len(universe),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Refresca company_snapshot desde yfinance.")
    p.add_argument("--limit", type=int, default=None, help="máximo de tickers a procesar")
    p.add_argument("--all", action="store_true", help="refrescar también los ya hechos")
    p.add_argument("--max-age-hours", type=float, default=None,
                   help="refrescar lo que falte + snapshots más viejos de N horas")
    p.add_argument("--pause", type=float, default=0.7, help="pausa (s) entre tickers")
    args = p.parse_args()

    summary = refresh_snapshots(limit=args.limit, only_missing=not args.all,
                                max_age_hours=args.max_age_hours, pause=args.pause)
    print(json.dumps(summary, indent=2))
