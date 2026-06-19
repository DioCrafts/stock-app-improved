"""Punto de entrada FastAPI.

Crea la app, configura CORS hacia el frontend (Vite) y monta los routers
(uno por área de la UI). Solo sirve la API: el job de ingesta corre en un
proceso aparte (app.jobs.scheduler), nunca aquí (ver H2).

Desarrollo:
    uv run uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.schema import connect, init_db
from app.routers import companies, financials, insiders, market, prices, screener, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegurar el esquema: en un despliegue limpio (volumen vacío) las tablas aún no
    # existen → sin esto los endpoints darían 500 en vez de devolver vacío.
    # El job pesado de ingesta corre en un PROCESO APARTE (app.jobs.scheduler),
    # nunca dentro del web (ver H2).
    conn = connect(settings.db_path)
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


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
app.include_router(insiders.router)
app.include_router(screener.router)
app.include_router(search.router)
app.include_router(market.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}
