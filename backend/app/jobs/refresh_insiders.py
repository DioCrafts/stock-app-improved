"""Job batch: ingesta de actividad de insiders (SEC Form 3/4/5) para el universo US.

Dos modos, ambos persisten en `insider_transaction` + `insider_summary`:

- **Incremental (por defecto)**: recorre los símbolos US y lee sus Form 4 recientes
  vía la submissions API de EDGAR (cacheado). Idempotente: `INSERT OR IGNORE` evita
  duplicar lo ya presente. Tolerante a fallos: un ticker que falla no aborta el lote.

- **Backfill histórico (`--backfill YYYYqQ`)**: descarga el dataset trimestral DERA
  "Form 345" y carga de golpe todas las operaciones del trimestre para el universo US.

Ejecutar manualmente:
    uv run python -m app.jobs.refresh_insiders                 # incremental (todos los US)
    uv run python -m app.jobs.refresh_insiders --limit 50      # incremental (smoke test)
    uv run python -m app.jobs.refresh_insiders --backfill 2025q1   # backfill un trimestre
    uv run python -m app.jobs.refresh_insiders --summaries-only    # recalcular resúmenes
"""
from __future__ import annotations

import time

from app.config import settings
from app.db import queries
from app.db.schema import connect, init_db
from app.ingest import edgar_client
from app.services.insider_service import build_summary_row


def _to_db_row(t: dict, source: str) -> dict:
    """Transacción normalizada (parser) → fila de `insider_transaction`."""
    return {
        "symbol": t["symbol"],
        "cik": t.get("cik"),
        "accession": t.get("accession"),
        "filer": t.get("filer"),
        "relationship": t.get("relationship"),
        "txn_date": t.get("txn_date"),
        "code": t.get("code"),
        "action": t.get("action"),
        "shares": t.get("shares"),
        "price": t.get("price"),
        "shares_after": t.get("shares_after"),
        "ownership": t.get("ownership"),
        "is_derivative": 1 if t.get("is_derivative") else 0,
        "source": source,
        "url": t.get("url"),
    }


def _store(conn, symbol: str, transactions: list[dict], source: str) -> int:
    """Persiste transacciones de un símbolo y recalcula su resumen. Devuelve nuevas filas."""
    rows = [_to_db_row(t, source) for t in transactions if t.get("symbol")]
    inserted = queries.upsert_insider_transactions(conn, rows)
    txns = queries.transactions_for_summary(conn, symbol)
    if txns:
        queries.upsert_insider_summary(conn, build_summary_row(symbol, txns))
    return inserted


def refresh_insiders(limit: int | None = None, pause: float = 0.2,
                     db_path: str | None = None, log_every: int = 50) -> dict:
    """Incremental: lee Form 4 recientes de cada símbolo US y los persiste."""
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        symbols = queries.us_symbols(conn, limit)
        processed = inserted = errors = 0
        for i, sym in enumerate(symbols, 1):
            try:
                raw = edgar_client.fetch_insider_transactions(
                    sym, max_filings=settings.insider_max_filings)
                inserted += _store(conn, sym, raw, source="edgar")
                processed += 1
            except Exception as err:  # noqa: BLE001 — un fallo no aborta el lote
                errors += 1
                if errors <= 10:
                    print(f"  ! {sym}: {err}", flush=True)
            if i % log_every == 0:
                print(f"  {i}/{len(symbols)} (nuevas={inserted} err={errors})", flush=True)
            if pause:
                time.sleep(pause)
        return {
            "mode": "incremental",
            "processed": processed,
            "inserted": inserted,
            "errors": errors,
            "symbols_with_data": len(queries.distinct_insider_symbols(conn)),
        }
    finally:
        conn.close()


def backfill_dera(year: int, quarter: int, db_path: str | None = None) -> dict:
    """Backfill: carga un trimestre completo del dataset DERA para el universo US."""
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        universe = set(queries.us_symbols(conn))
        raw = edgar_client.fetch_dera_quarter(year, quarter, symbols=universe)
        rows = [_to_db_row(t, "dera") for t in raw if t.get("symbol")]
        inserted = queries.upsert_insider_transactions(conn, rows)
        affected = sorted({r["symbol"] for r in rows})
        for sym in affected:
            txns = queries.transactions_for_summary(conn, sym)
            if txns:
                queries.upsert_insider_summary(conn, build_summary_row(sym, txns))
        return {
            "mode": f"backfill {year}q{quarter}",
            "transactions_parsed": len(raw),
            "inserted": inserted,
            "symbols_affected": len(affected),
        }
    finally:
        conn.close()


def recompute_summaries(db_path: str | None = None) -> dict:
    """Recalcula `insider_summary` para todos los símbolos con transacciones."""
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        symbols = queries.distinct_insider_symbols(conn)
        for sym in symbols:
            txns = queries.transactions_for_summary(conn, sym)
            if txns:
                queries.upsert_insider_summary(conn, build_summary_row(sym, txns))
        return {"mode": "summaries-only", "symbols": len(symbols)}
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Ingesta de insiders desde SEC EDGAR (solo US).")
    p.add_argument("--limit", type=int, default=None, help="máximo de tickers (incremental)")
    p.add_argument("--pause", type=float, default=0.2, help="pausa (s) entre tickers")
    p.add_argument("--backfill", type=str, default=None, metavar="YYYYqQ",
                   help="cargar un trimestre DERA, p. ej. 2025q1")
    p.add_argument("--summaries-only", action="store_true", help="solo recalcular resúmenes")
    args = p.parse_args()

    if args.summaries_only:
        summary = recompute_summaries()
    elif args.backfill:
        y, q = args.backfill.lower().split("q")
        summary = backfill_dera(int(y), int(q))
    else:
        summary = refresh_insiders(limit=args.limit, pause=args.pause)
    print(json.dumps(summary, indent=2))
