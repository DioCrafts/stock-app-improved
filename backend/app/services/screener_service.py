"""Screener server-side → pantalla Screener.

Traduce los filtros del front (FILTER_DEFS) a una consulta sobre `company_snapshot`
y devuelve compañías paginadas. Los filtros de score (valueMin/growthMin/...) no
devolverán nada hasta que la Fase 5 rellene los scores (hoy NULL = excluido, igual
que `matchPass` del front cuando el valor es null).
"""
from __future__ import annotations

from app.config import settings
from app.db import queries
from app.db.schema import connect
from app.models.company import Company


def screen(filters: dict, sort: str = "composite", order: str = "desc",
           limit: int = 50, offset: int = 0) -> dict:
    conn = connect(settings.db_path)
    try:
        total, blobs = queries.screen(conn, filters, sort, order, limit, offset)
    finally:
        conn.close()
    results = [Company.model_validate_json(b) for b in blobs if b]
    return {"total": total, "count": len(results), "results": results}
