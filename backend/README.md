# Backend — Equity Research Terminal

API FastAPI que sustituye el mock de `src/data.js`, ingiriendo datos con **yfinance**
(fundamentales/precios) y **SEC EDGAR** (actividad de insiders, solo US).
Mercados contemplados: **EE.UU., Canadá y Reino Unido**.
Diseño completo en [../ARQUITECTURA-BACKEND.md](../ARQUITECTURA-BACKEND.md).

## Requisitos
- [uv](https://docs.astral.sh/uv/) — gestiona Python 3.12 automáticamente (no usar el Python del sistema).

## Puesta en marcha
```bash
cp .env.example .env
uv sync                                  # crea .venv e instala dependencias
uv run uvicorn app.main:app --reload     # http://localhost:8000
```
- Health check: `http://localhost:8000/health`
- OpenAPI / Swagger: `http://localhost:8000/docs`

## Tests
```bash
uv run pytest
```

## Estructura (resumen)
```
app/
  main.py        # FastAPI + CORS + montaje de routers
  config.py      # settings (pydantic-settings)
  models/        # Pydantic = contrato 1:1 con src/data.js
  routers/       # un archivo por área de la UI
  services/      # lógica de negocio (orquesta ingest + scoring + db)
  universe/      # descubrimiento de tickers US/CA/UK
  ingest/        # ÚNICO punto que conoce las APIs externas (yfinance, SEC EDGAR)
  db/            # persistencia SQLite (snapshot del universo + insiders)
  jobs/          # ingesta batch programada
  cache/         # caché TTL en disco
tests/
```

## Insiders (compras/ventas de directivos) — US + UK

Actividad de insiders: compras/ventas de directivos, consejeros y accionistas >10%.
Dos mercados, dos fuentes **oficiales y gratuitas**; ambas desembocan en las mismas
tablas, métricas, endpoint y widget (solo cambia la ingesta).

**🇺🇸 EE.UU. — SEC EDGAR** (`ingest/edgar_client.py`, parsers en `ingest/insider_mappers.py`):
- **Incremental** (submissions API + XML del Form 4) — refresco diario.
- **Backfill histórico** (datasets trimestrales DERA "Form 345").

```bash
uv run python -m app.jobs.refresh_insiders              # incremental (todos los US)
uv run python -m app.jobs.refresh_insiders --limit 50   # smoke test (50 tickers)
uv run python -m app.jobs.refresh_insiders --backfill 2025q1   # backfill un trimestre
```

**🇬🇧 Reino Unido — FCA National Storage Mechanism** (`ingest/nsm_client.py`, parser de la
plantilla MAR en `ingest/nsm_mappers.py`): barrido de las notificaciones PDMR (Art. 19 de
UK MAR) por fecha, casadas con el universo por nombre de empresa. El NSM es el repositorio
oficial del regulador (equivalente a EDGAR); su API de búsqueda es pública y sin clave.

```bash
uv run python -m app.jobs.refresh_insiders --market uk                    # barrido reciente
uv run python -m app.jobs.refresh_insiders --market uk --since-days 365   # ventana mayor
```

> ⚠️ Tanto la SEC como el FCA piden un **User-Agent identificable con tu email** (*fair
> access*): configura `SEC_USER_AGENT` y `NSM_USER_AGENT` o pueden devolver `403`.
> El NSM no es tiempo real (~48 h de retraso). El parsing del documento MAR (HTML de Word)
> es best-effort: los recuentos compra/venta son fiables; algún importe puede quedar a `—`.

Endpoint: `GET /companies/{ticker}/insiders` → resumen por ventanas (30/90/180/365 d) +
operaciones recientes (divisa USD para US, GBP para UK). Filtros de screener:
`insiderNetMin` (compra neta 6m) y `insiderBuysMin`. Canadá aún no tiene fuente integrada.
