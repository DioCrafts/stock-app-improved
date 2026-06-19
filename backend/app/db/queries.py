"""Consultas SQL sobre el snapshot/universo (stdlib sqlite3).

Fase 2: operaciones sobre `universe`. Las de companies/search/screener llegan en
Fase 4/6 cuando exista `company_snapshot`.
"""
from __future__ import annotations

import re
import sqlite3

_UNIVERSE_COLS = ("symbol", "name", "exchange", "market", "currency", "sector", "country", "market_cap")


def replace_universe(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Reemplaza por completo el contenido de `universe` (refresco idempotente)."""
    conn.execute("DELETE FROM universe")
    conn.executemany(
        "INSERT OR REPLACE INTO universe "
        "(symbol, name, exchange, market, currency, sector, country, market_cap, updated_at) "
        "VALUES (:symbol, :name, :exchange, :market, :currency, :sector, :country, :market_cap, "
        "datetime('now'))",
        rows,
    )
    conn.commit()


def count_universe(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]


def counts_by_market(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute("SELECT market, COUNT(*) AS c FROM universe GROUP BY market ORDER BY market")
    return {row["market"]: row["c"] for row in cur.fetchall()}


def universe_rows(conn: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    """Símbolos del universo (símbolo + mercado) para alimentar la ingesta."""
    sql = "SELECT symbol, market FROM universe ORDER BY symbol"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql).fetchall()]


# ---- company_snapshot ----

_SNAPSHOT_COLS = (
    "symbol", "name", "market", "sector", "price", "change", "market_cap",
    "pe", "peg", "pb", "div_yield", "roe", "rev_growth",
    "score_value", "score_growth", "score_health", "score_momentum", "score_composite",
    "ret_1y", "px_vs_200d",
    "data", "status", "error",
)


def upsert_snapshots(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Inserta/actualiza filas de snapshot (idempotente por símbolo)."""
    placeholders = ", ".join(f":{c}" for c in _SNAPSHOT_COLS)
    cols = ", ".join(_SNAPSHOT_COLS)
    conn.executemany(
        f"INSERT OR REPLACE INTO company_snapshot ({cols}, updated_at) "
        f"VALUES ({placeholders}, datetime('now'))",
        rows,
    )
    conn.commit()


def count_snapshots(conn: sqlite3.Connection, status: str | None = None) -> int:
    if status:
        return conn.execute(
            "SELECT COUNT(*) FROM company_snapshot WHERE status = ?", (status,)
        ).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM company_snapshot").fetchone()[0]


def snapshot_symbols(conn: sqlite3.Connection, status: str | None = None) -> set[str]:
    """Conjunto de símbolos ya con snapshot (para reanudar la ingesta)."""
    if status:
        cur = conn.execute("SELECT symbol FROM company_snapshot WHERE status = ?", (status,))
    else:
        cur = conn.execute("SELECT symbol FROM company_snapshot")
    return {r["symbol"] for r in cur.fetchall()}


def fresh_symbols(conn: sqlite3.Connection, max_age_hours: float) -> set[str]:
    """Símbolos con snapshot OK actualizado dentro de las últimas `max_age_hours`
    (para el refresco por antigüedad: solo se re-procesa lo viejo)."""
    cur = conn.execute(
        "SELECT symbol FROM company_snapshot WHERE status = 'ok' AND updated_at >= datetime('now', ?)",
        (f"-{float(max_age_hours)} hours",),
    )
    return {r["symbol"] for r in cur.fetchall()}


def get_snapshot(conn: sqlite3.Connection, symbol: str) -> dict | None:
    row = conn.execute("SELECT * FROM company_snapshot WHERE symbol = ?", (symbol,)).fetchone()
    return dict(row) if row else None


def all_snapshots_for_scoring(conn: sqlite3.Connection) -> list[dict]:
    """Datos necesarios para puntuar todo el universo (status ok)."""
    rows = conn.execute(
        "SELECT symbol, market, data, ret_1y, px_vs_200d FROM company_snapshot WHERE status = 'ok'"
    ).fetchall()
    return [dict(r) for r in rows]


def update_scores(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Actualiza columnas de score + el blob `data` (Company con scores embebidos)."""
    conn.executemany(
        "UPDATE company_snapshot SET "
        "score_value=:score_value, score_growth=:score_growth, score_health=:score_health, "
        "score_momentum=:score_momentum, score_composite=:score_composite, data=:data "
        "WHERE symbol=:symbol",
        rows,
    )
    conn.commit()


def list_company_data(conn: sqlite3.Connection, limit: int = 50, offset: int = 0) -> list[str]:
    """Blobs JSON de Company (status ok), ordenados por market cap desc (nulls al final)."""
    rows = conn.execute(
        "SELECT data FROM company_snapshot WHERE status = 'ok' "
        "ORDER BY market_cap DESC LIMIT ? OFFSET ?",  # DESC ya deja los NULL al final (usa índice)
        (limit, offset),
    ).fetchall()
    return [r["data"] for r in rows]


def snapshots_by_symbols(conn: sqlite3.Connection, symbols: list[str]) -> dict[str, str]:
    """Blobs JSON (status ok) de varios símbolos en UNA sola query (evita N conexiones, M6)."""
    if not symbols:
        return {}
    placeholders = ",".join("?" * len(symbols))
    rows = conn.execute(
        f"SELECT symbol, data FROM company_snapshot WHERE status = 'ok' AND symbol IN ({placeholders})",
        list(symbols),
    ).fetchall()
    return {r["symbol"]: r["data"] for r in rows}


# ---- insiders (SEC Form 3/4/5, solo US) ----

_INSIDER_TXN_COLS = (
    "symbol", "cik", "accession", "filer", "relationship", "txn_date", "code", "action",
    "shares", "price", "shares_after", "ownership", "is_derivative", "source", "url",
)


def upsert_insider_transactions(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Inserta transacciones de insiders (INSERT OR IGNORE → dedup por UNIQUE).
    Devuelve cuántas filas nuevas se insertaron."""
    if not rows:
        return 0
    placeholders = ", ".join(f":{c}" for c in _INSIDER_TXN_COLS)
    cols = ", ".join(_INSIDER_TXN_COLS)
    before = conn.total_changes
    conn.executemany(
        f"INSERT OR IGNORE INTO insider_transaction ({cols}, updated_at) "
        f"VALUES ({placeholders}, datetime('now'))",
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def insider_transactions_for(conn: sqlite3.Connection, symbol: str, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM insider_transaction WHERE symbol = ? ORDER BY txn_date DESC LIMIT ?",
        (symbol, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def transactions_for_summary(conn: sqlite3.Connection, symbol: str) -> list[dict]:
    """Campos mínimos para recalcular agregados (los lee insider_metrics.summarize)."""
    rows = conn.execute(
        "SELECT txn_date, code, shares, price, filer FROM insider_transaction WHERE symbol = ?",
        (symbol,),
    ).fetchall()
    return [dict(r) for r in rows]


def distinct_insider_symbols(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT symbol FROM insider_transaction ORDER BY symbol")
    return [r["symbol"] for r in cur.fetchall()]


def upsert_insider_summary(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO insider_summary "
        "(symbol, buys_6m, sells_6m, net_value_6m, last_txn_date, currency, data, updated_at) "
        "VALUES (:symbol, :buys_6m, :sells_6m, :net_value_6m, :last_txn_date, :currency, :data, "
        "datetime('now'))",
        row,
    )
    conn.commit()


def get_insider_summary(conn: sqlite3.Connection, symbol: str) -> dict | None:
    row = conn.execute("SELECT * FROM insider_summary WHERE symbol = ?", (symbol,)).fetchone()
    return dict(row) if row else None


def us_symbols(conn: sqlite3.Connection, limit: int | None = None) -> list[str]:
    """Símbolos US del universo (la actividad de insiders SEC es solo US)."""
    sql = "SELECT symbol FROM universe WHERE market = 'US' ORDER BY symbol"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [r["symbol"] for r in conn.execute(sql).fetchall()]


def uk_universe_names(conn: sqlite3.Connection) -> list[dict]:
    """(symbol, name) del universo UK, para casar por nombre con los avisos PDMR del NSM."""
    rows = conn.execute(
        "SELECT symbol, name FROM universe WHERE market = 'UK' AND name IS NOT NULL"
    ).fetchall()
    return [dict(r) for r in rows]


def rebuild_universe_fts(conn: sqlite3.Connection) -> None:
    """Reconstruye el índice FTS5 de búsqueda a partir de `universe` (L7)."""
    conn.execute("DELETE FROM universe_fts")
    conn.execute("INSERT INTO universe_fts(symbol, name) SELECT symbol, name FROM universe")
    conn.commit()


def search_universe(conn: sqlite3.Connection, q: str, limit: int = 10) -> list[dict]:
    """Busca por ticker/nombre con FTS5 (prefijo por token, O(log n)); LIKE como respaldo.
    Los tokens se sanean a alfanuméricos → sin comodines ni operadores FTS del usuario (L3)."""
    tokens = re.findall(r"[A-Za-z0-9]+", q)
    if not tokens:
        return []
    exact = q.strip().upper()
    try:
        match = " ".join(f"{t}*" for t in tokens)
        rows = conn.execute(
            "SELECT f.symbol, u.name, s.price, s.score_composite "
            "FROM universe_fts f "
            "JOIN universe u ON u.symbol = f.symbol "
            "LEFT JOIN company_snapshot s ON s.symbol = f.symbol "
            "WHERE universe_fts MATCH ? "
            "ORDER BY (u.symbol = ?) DESC, rank LIMIT ?",
            (match, exact, limit),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        pass  # FTS no disponible/poblado → respaldo LIKE
    like = f"%{tokens[0]}%"
    rows = conn.execute(
        "SELECT u.symbol, u.name, s.price, s.score_composite "
        "FROM universe u LEFT JOIN company_snapshot s ON u.symbol = s.symbol "
        "WHERE u.symbol LIKE ? OR u.name LIKE ? "
        "ORDER BY (u.symbol = ?) DESC, length(u.symbol) LIMIT ?",
        (like, like, exact, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# Mapeo filtro del front (FILTER_DEFS) → (columna, operador)
_SCREEN_FILTERS = {
    "capMin": ("market_cap", ">="),
    "peMax": ("pe", "<="),
    "pegMax": ("peg", "<="),
    "pbMax": ("pb", "<="),
    "divMin": ("div_yield", ">="),
    "roeMin": ("roe", ">="),
    "growthRevMin": ("rev_growth", ">="),
    "valueMin": ("score_value", ">="),
    "growthMin": ("score_growth", ">="),
    "healthMin": ("score_health", ">="),
    "momentumMin": ("score_momentum", ">="),
}
# Claves de orden del front → expresión SQL ("symbol"/"insider" se cualifican por el JOIN)
_SORT_COLS = {
    "composite": "score_composite", "value": "score_value", "growth": "score_growth",
    "marketCap": "market_cap", "pe": "pe", "peg": "peg", "div": "div_yield",
    "roe": "roe", "rev": "rev_growth", "price": "price", "ticker": "company_snapshot.symbol",
    "insider": "isum.net_value_6m",
}
# Filtros de insiders → (columna en insider_summary, operador). Activan un JOIN.
_INSIDER_FILTERS = {
    "insiderNetMin": ("isum.net_value_6m", ">="),   # neto comprado últimos 6m ≥ X ($M)
    "insiderBuysMin": ("isum.buys_6m", ">="),       # nº de compras últimos 6m ≥ N
}


def screen(conn: sqlite3.Connection, filters: dict, sort: str = "composite",
           order: str = "desc", limit: int = 50, offset: int = 0) -> tuple[int, list[str]]:
    """Filtra el snapshot (espejo de matchPass del front: null en la columna = excluido).
    Devuelve (total, [blobs JSON de Company]). Los filtros/orden de insiders añaden un
    JOIN a insider_summary solo cuando se usan (el screening normal no se penaliza)."""
    sort_col = _SORT_COLS.get(sort, "score_composite")
    order_sql = "DESC" if order.lower() == "desc" else "ASC"

    where = ["status = 'ok'", f"{sort_col} IS NOT NULL"]
    params: list = []
    for key, (col, op) in _SCREEN_FILTERS.items():
        v = filters.get(key)
        if v is not None:
            where.append(f"{col} {op} ?")
            params.append(v)

    insider_active = sort == "insider"
    for key, (col, op) in _INSIDER_FILTERS.items():
        v = filters.get(key)
        if v is not None:
            where.append(f"{col} {op} ?")
            params.append(v)
            insider_active = True

    from_sql = "company_snapshot"
    if insider_active:  # INNER JOIN: filtrar/ordenar por insiders exige tener resumen
        from_sql += " JOIN insider_summary isum ON isum.symbol = company_snapshot.symbol"
    where_sql = " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) FROM {from_sql} WHERE {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT company_snapshot.data FROM {from_sql} WHERE {where_sql} "
        f"ORDER BY {sort_col} {order_sql} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return total, [r["data"] for r in rows]
