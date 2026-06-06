"""Punto de entrada FastAPI.

Crea la app, configura CORS hacia el frontend (Vite) y monta los routers
(uno por área de la UI). El scheduler de ingesta se arrancará en el lifespan
(pendiente: Fase 4).

Desarrollo:
    uv run uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.schema import connect, init_db
from app.routers import companies, financials, market, prices, screener, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegurar el esquema: en un despliegue limpio (volumen vacío) las tablas aún no
    # existen → sin esto los endpoints darían 500 en vez de devolver vacío.
    _conn = connect(settings.db_path)
    try:
        init_db(_conn)
    finally:
        _conn.close()

    scheduler = None
    if settings.enable_scheduler:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        from app.jobs.refresh_snapshots import refresh_snapshots
        from app.jobs.score_snapshots import score_universe
        from app.universe.refresh import refresh_universe

        def scheduled_refresh():
            # universo → fundamentales (lo que falte + lo más viejo de N horas) → scores
            refresh_universe()
            refresh_snapshots(max_age_hours=settings.refresh_max_age_hours)
            score_universe()

        scheduler = BackgroundScheduler()
        scheduler.add_job(scheduled_refresh, CronTrigger.from_crontab(settings.refresh_cron), id="refresh_snapshots")
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Equity Research Terminal — API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Un router por área de la UI (ver app/routers/*)
app.include_router(companies.router)
app.include_router(prices.router)
app.include_router(financials.router)
app.include_router(screener.router)
app.include_router(search.router)
app.include_router(market.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}
