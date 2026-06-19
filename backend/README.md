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

## Insiders (SEC EDGAR — solo US)

Actividad de insiders (Section 16, Form 3/4/5): compras/ventas de directivos, consejeros
y accionistas >10%. Dos fuentes oficiales y gratuitas, ambas en `ingest/edgar_client.py`
(parsers puros en `ingest/insider_mappers.py`):

- **Incremental** (submissions API + XML del Form 4) — refresco diario.
- **Backfill histórico** (datasets trimestrales DERA "Form 345").

```bash
uv run python -m app.jobs.refresh_insiders              # incremental (todos los US)
uv run python -m app.jobs.refresh_insiders --limit 50   # smoke test (50 tickers)
uv run python -m app.jobs.refresh_insiders --backfill 2025q1   # backfill un trimestre
```

> ⚠️ La SEC exige un **User-Agent identificable con tu email** (política de *fair access*):
> configúralo en `SEC_USER_AGENT` o EDGAR puede devolver `403`.

Endpoint: `GET /companies/{ticker}/insiders` → resumen por ventanas (30/90/180/365 d) +
operaciones recientes. Filtros de screener: `insiderNetMin` (compra neta 6m, $M) y
`insiderBuysMin`. Para tickers no-US (UK/CA) el bundle viene vacío (no hay equivalente SEC).
