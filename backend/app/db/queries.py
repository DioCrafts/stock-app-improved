"""Consultas SQL sobre el snapshot/universo (stdlib sqlite3).

Fase 2: operaciones sobre `universe`. Las de companies/search/screener llegan en
Fase 4/6 cuando exista `company_snapshot`.
"""
from __future__ import annotations

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


def search_universe(conn: sqlite3.Connection, q: str, limit: int = 10) -> list[dict]:
    """Busca por ticker o nombre en el universo; añade price/composite del snapshot si existe."""
    like = f"%{q}%"
    rows = conn.execute(
        "SELECT u.symbol, u.name, s.price, s.score_composite "
        "FROM universe u LEFT JOIN company_snapshot s ON u.symbol = s.symbol "
        "WHERE u.symbol LIKE ? OR u.name LIKE ? "
        "ORDER BY (u.symbol = ?) DESC, length(u.symbol) LIMIT ?",
        (like, like, q.upper(), limit),
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
# Claves de orden del front → columna
_SORT_COLS = {
    "composite": "score_composite", "value": "score_value", "growth": "score_growth",
    "marketCap": "market_cap", "pe": "pe", "peg": "peg", "div": "div_yield",
    "roe": "roe", "rev": "rev_growth", "price": "price", "ticker": "symbol",
}


def screen(conn: sqlite3.Connection, filters: dict, sort: str = "composite",
           order: str = "desc", limit: int = 50, offset: int = 0) -> tuple[int, list[str]]:
    """Filtra el snapshot (espejo de matchPass del front: null en la columna = excluido).
    Devuelve (total, [blobs JSON de Company])."""
    sort_col = _SORT_COLS.get(sort, "score_composite")
    order_sql = "DESC" if order.lower() == "desc" else "ASC"

    # Ordenar por una columna exige tenerla (NULL fuera) → permite usar índice y evita
    # el `ORDER BY col IS NULL, col` que forzaba full scan + temp B-TREE (M5).
    where = ["status = 'ok'", f"{sort_col} IS NOT NULL"]
    params: list = []
    for key, (col, op) in _SCREEN_FILTERS.items():
        v = filters.get(key)
        if v is not None:
            where.append(f"{col} {op} ?")
            params.append(v)
    where_sql = " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) FROM company_snapshot WHERE {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT data FROM company_snapshot WHERE {where_sql} "
        f"ORDER BY {sort_col} {order_sql} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return total, [r["data"] for r in rows]
