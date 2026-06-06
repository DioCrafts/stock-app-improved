"""Construye/actualiza la tabla `universe` en DB a partir de los providers.

Ejecutar manualmente:
    uv run python -m app.universe.refresh
"""
from __future__ import annotations

from app.config import settings
from app.db import queries
from app.db.schema import connect, init_db
from app.universe.providers import fetch_universe


def refresh_universe(db_path: str | None = None) -> dict[str, int]:
    """Recarga el universo completo en SQLite. Devuelve el recuento por mercado."""
    rows = fetch_universe()
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        queries.replace_universe(conn, rows)
        queries.rebuild_universe_fts(conn)  # mantener el índice de búsqueda al día (L7)
        return queries.counts_by_market(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    import json

    counts = refresh_universe()
    total = sum(counts.values())
    print(json.dumps({"by_market": counts, "total": total}, indent=2))
