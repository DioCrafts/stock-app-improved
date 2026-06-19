"""Esquema SQLite y conexión.

SQLite (un fichero, sin servidor) por KISS; justificado por el tamaño del universo
US+CA+UK (~16k símbolos). stdlib `sqlite3`, sin ORM.

- `universe`: catálogo de tickers (Fase 2).
- `company_snapshot`: fundamentales pre-calculados de todo el universo (Fase 4).
  Columnas indexables = los campos por los que filtra/ordena el screener; `data` = JSON
  del `Company` completo (para la ficha/lista/compare sin llamar a yfinance en caliente).
"""
from __future__ import annotations

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS universe (
    symbol      TEXT PRIMARY KEY,   -- símbolo yfinance (AAPL, SHOP.TO, HSBA.L)
    name        TEXT,
    exchange    TEXT,               -- código FinanceDatabase (NYQ, TOR, LSE...)
    market      TEXT,               -- US | CA | UK
    currency    TEXT,
    sector      TEXT,
    country     TEXT,
    market_cap  TEXT,               -- bucket categórico de FinanceDatabase
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_universe_market ON universe(market);
CREATE INDEX IF NOT EXISTS idx_universe_name   ON universe(name);

CREATE TABLE IF NOT EXISTS company_snapshot (
    symbol          TEXT PRIMARY KEY,
    name            TEXT,
    market          TEXT,
    sector          TEXT,
    -- columnas para filtrar/ordenar el screener (espejo de FILTER_DEFS)
    price           REAL,
    change          REAL,
    market_cap      REAL,
    pe              REAL,
    peg             REAL,
    pb              REAL,
    div_yield       REAL,
    roe             REAL,
    rev_growth      REAL,
    score_value     INTEGER,
    score_growth    INTEGER,
    score_health    INTEGER,
    score_momentum  INTEGER,
    score_composite INTEGER,
    -- inputs crudos de momentum (capturados en la ingesta, usados por el scoring)
    ret_1y          REAL,           -- 52WeekChange (retorno 1 año, fracción)
    px_vs_200d      REAL,           -- precio / media 200d - 1
    -- Company completo (JSON) + estado de ingesta
    data            TEXT,
    status          TEXT,           -- 'ok' | 'error'
    error           TEXT,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_market       ON company_snapshot(market);
CREATE INDEX IF NOT EXISTS idx_snap_composite    ON company_snapshot(score_composite);
CREATE INDEX IF NOT EXISTS idx_snap_pe           ON company_snapshot(pe);
CREATE INDEX IF NOT EXISTS idx_snap_marketcap    ON company_snapshot(market_cap);
-- resto de columnas de orden/filtro del screener (M5/L6)
CREATE INDEX IF NOT EXISTS idx_snap_score_value  ON company_snapshot(score_value);
CREATE INDEX IF NOT EXISTS idx_snap_score_growth ON company_snapshot(score_growth);
CREATE INDEX IF NOT EXISTS idx_snap_peg          ON company_snapshot(peg);
CREATE INDEX IF NOT EXISTS idx_snap_pb           ON company_snapshot(pb);
CREATE INDEX IF NOT EXISTS idx_snap_div_yield    ON company_snapshot(div_yield);
CREATE INDEX IF NOT EXISTS idx_snap_roe          ON company_snapshot(roe);
CREATE INDEX IF NOT EXISTS idx_snap_rev_growth   ON company_snapshot(rev_growth);
CREATE INDEX IF NOT EXISTS idx_snap_price        ON company_snapshot(price);

-- Índice de búsqueda FTS5 (ticker + nombre) para /search en O(log n) (L7)
CREATE VIRTUAL TABLE IF NOT EXISTS universe_fts USING fts5(symbol, name);

-- Insiders (SEC Form 3/4/5, solo US). Detalle de operaciones declaradas.
-- UNIQUE evita duplicar la misma línea entre el backfill DERA y el incremental EDGAR.
CREATE TABLE IF NOT EXISTS insider_transaction (
    symbol        TEXT NOT NULL,
    cik           TEXT,
    accession     TEXT,              -- nº de filing
    filer         TEXT,              -- nombre del insider
    relationship  TEXT,              -- Director / Officer (CEO) / 10% Owner…
    txn_date      TEXT,              -- ISO yyyy-mm-dd
    code          TEXT,              -- P,S,A,M,F,G,C,X…
    action        TEXT,              -- buy|sell|grant|exercise|gift|tax|conversion|other
    shares        REAL,
    price         REAL,              -- por acción (USD)
    shares_after  REAL,
    ownership     TEXT,              -- D|I
    is_derivative INTEGER,           -- 0|1
    source        TEXT,              -- 'dera' | 'edgar'
    url           TEXT,
    updated_at    TEXT,
    UNIQUE(accession, symbol, txn_date, code, shares, price, is_derivative)
);
CREATE INDEX IF NOT EXISTS idx_insider_symbol ON insider_transaction(symbol);
CREATE INDEX IF NOT EXISTS idx_insider_date   ON insider_transaction(txn_date);

-- Resumen por empresa (agregados de mercado abierto). Columnas indexadas para el
-- screener (LEFT JOIN solo cuando hay filtro de insiders activo) + `data` con el
-- bundle completo de ventanas para la ficha.
CREATE TABLE IF NOT EXISTS insider_summary (
    symbol        TEXT PRIMARY KEY,
    buys_6m       INTEGER,
    sells_6m      INTEGER,
    net_value_6m  REAL,              -- compras − ventas (mercado abierto), en $M, 180d
    last_txn_date TEXT,
    data          TEXT,              -- JSON: list[InsiderWindow]
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_insider_summary_net6m ON insider_summary(net_value_6m);
CREATE INDEX IF NOT EXISTS idx_insider_summary_buys6m ON insider_summary(buys_6m);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Abre una conexión, creando el directorio padre si hace falta.
    Activa WAL para que la API (lecturas) y el job batch (escrituras) no se bloqueen."""
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
