"""Pasada de scoring: calcula los scores de todo el snapshot y los persiste.

Lee `company_snapshot` (status ok), calcula percentiles por mercado y reescribe
las columnas `score_*` + embebe los scores en el `Company` (blob `data`).
Debe ejecutarse DESPUÉS de la ingesta (necesita el universo para los percentiles).

    uv run python -m app.jobs.score_snapshots
"""
from __future__ import annotations

from app.config import settings
from app.db import queries
from app.db.schema import connect, init_db
from app.models.company import Company
from app.services import scoring


def score_universe(db_path: str | None = None) -> dict:
    conn = connect(db_path or settings.db_path)
    try:
        init_db(conn)
        snaps = queries.all_snapshots_for_scoring(conn)
        records: list[dict] = []
        companies: dict[str, Company] = {}
        for s in snaps:
            if not s["data"]:
                continue
            c = Company.model_validate_json(s["data"])
            companies[s["symbol"]] = c
            records.append({
                "symbol": s["symbol"],
                "market": s["market"],
                "factors": scoring.company_factors(c, s["ret_1y"], s["px_vs_200d"]),
            })

        scores = scoring.compute_scores(records)

        updates = []
        for symbol, sc in scores.items():
            company = companies[symbol]
            company.scores = sc
            updates.append({
                "symbol": symbol,
                "score_value": sc.value, "score_growth": sc.growth, "score_health": sc.health,
                "score_momentum": sc.momentum, "score_composite": sc.composite,
                "data": company.model_dump_json(),
            })
        queries.update_scores(conn, updates)

        return {
            "scored": len(updates),
            "with_composite": sum(1 for u in updates if u["score_composite"] is not None),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import json

    print(json.dumps(score_universe(), indent=2))
