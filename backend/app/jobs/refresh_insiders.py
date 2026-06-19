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
from datetime import date, timedelta

from app.config import settings
from app.db import queries
from app.db.schema import connect, init_db
from app.ingest import edgar_client, nsm_client
from app.ingest.nsm_mappers import normalize_company_name, parse_nsm_document
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


def _store(conn, symbol: str, transactions: list[dict], source: str, currency: str = "USD") -> int:
    """Persiste transacciones de un símbolo y recalcula su resumen. Devuelve nuevas filas."""
    rows = [_to_db_row(t, source) for t in transactions if t.get("symbol")]
    inserted = queries.upsert_insider_transactions(conn, rows)
    txns = queries.transactions_for_summary(conn, symbol)
    if txns:
        queries.upsert_insider_summary(conn, build_summary_row(symbol, txns, currency))
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


_UK_PDMR_TYPES = {"DSH"}  # Director/PDMR Shareholding (categoría principal del NSM)


def _pub_date(src: dict) -> date | None:
    raw = (src.get("publication_date") or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def refresh_insiders_uk(since_days: int | None = None, max_pages: int | None = None,
                        page_size: int = 100, pause: float = 0.3,
                        db_path: str | None = None, log_every: int = 5) -> dict:
    """Barrido del FCA NSM: notificaciones PDMR recientes → universo UK (solo .L).

    Recorre páginas de avisos PDMR (orden publicación desc) hasta superar la ventana
    `since_days`, casa la empresa con el universo por nombre, descarga y parsea el
    documento (plantilla MAR) y persiste. Idempotente (INSERT OR IGNORE)."""
    since_days = settings.insider_uk_since_days if since_days is None else since_days
    max_pages = settings.insider_uk_max_pages if max_pages is None else max_pages
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        name_map = {normalize_company_name(u["name"]): u["symbol"]
                    for u in queries.uk_universe_names(conn)}
        cutoff = date.today() - timedelta(days=since_days)
        per_symbol: dict[str, list[dict]] = {}
        seen: set[str] = set()
        scanned = matched = docs = errors = 0
        stop = False
        for page in range(max_pages):
            try:
                _total, hits = nsm_client.search_pdmr_page(from_=page * page_size, size=page_size)
            except Exception as err:  # noqa: BLE001 — fallo de búsqueda → cortar barrido
                print(f"  ! search page {page}: {err}", flush=True)
                break
            if not hits:
                break
            for src in hits:
                scanned += 1
                pd = _pub_date(src)
                if pd and pd < cutoff:
                    stop = True
                    continue
                head = src.get("headline") or ""
                if (src.get("type_code") or "").upper() not in _UK_PDMR_TYPES \
                        and "PDMR" not in head and "Director" not in head:
                    continue
                symbol = name_map.get(normalize_company_name(src.get("company")))
                link = src.get("download_link")
                if not symbol or not link or link in seen:
                    continue
                seen.add(link)
                matched += 1
                try:
                    html = nsm_client.fetch_artefact(link)
                    txns = parse_nsm_document(
                        html, symbol=symbol, company=src.get("company"), lei=src.get("lei"),
                        accession=src.get("disclosure_id"), url=nsm_client.artefact_url(link))
                    if txns:
                        per_symbol.setdefault(symbol, []).extend(txns)
                        docs += 1
                except Exception as err:  # noqa: BLE001 — un documento roto no aborta el barrido
                    errors += 1
                    if errors <= 10:
                        print(f"  ! {symbol} {link}: {err}", flush=True)
                if pause:
                    time.sleep(pause)
            if (page + 1) % log_every == 0:
                print(f"  page {page + 1}/{max_pages} scanned={scanned} matched={matched} "
                      f"docs={docs}", flush=True)
            if stop:
                break
        inserted = 0
        for symbol, txns in per_symbol.items():
            inserted += _store(conn, symbol, txns, source="nsm", currency="GBP")
        return {
            "mode": "uk-incremental",
            "scanned": scanned, "matched": matched, "docs_parsed": docs,
            "inserted": inserted, "symbols": len(per_symbol), "errors": errors,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Ingesta de insiders: SEC EDGAR (US) / FCA NSM (UK).")
    p.add_argument("--market", choices=["us", "uk"], default="us", help="mercado (def. us)")
    p.add_argument("--limit", type=int, default=None, help="US: máximo de tickers (incremental)")
    p.add_argument("--pause", type=float, default=None, help="pausa (s) entre peticiones")
    p.add_argument("--backfill", type=str, default=None, metavar="YYYYqQ",
                   help="US: cargar un trimestre DERA, p. ej. 2025q1")
    p.add_argument("--since-days", type=int, default=None, help="UK: ventana del barrido NSM")
    p.add_argument("--max-pages", type=int, default=None, help="UK: tope de páginas del barrido")
    p.add_argument("--summaries-only", action="store_true", help="solo recalcular resúmenes")
    args = p.parse_args()

    if args.summaries_only:
        summary = recompute_summaries()
    elif args.market == "uk":
        summary = refresh_insiders_uk(since_days=args.since_days, max_pages=args.max_pages,
                                      pause=args.pause if args.pause is not None else 0.3)
    elif args.backfill:
        y, q = args.backfill.lower().split("q")
        summary = backfill_dera(int(y), int(q))
    else:
        summary = refresh_insiders(limit=args.limit,
                                   pause=args.pause if args.pause is not None else 0.7)
    print(json.dumps(summary, indent=2))
