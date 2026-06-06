# Backend — Equity Research Terminal

API FastAPI que sustituye el mock de `src/data.js`, ingiriendo datos con **yfinance**.
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
  ingest/        # ÚNICO punto que conoce yfinance
  db/            # persistencia SQLite (snapshot del universo)
  jobs/          # ingesta batch programada
  cache/         # caché TTL en disco
tests/
```

> Estado: **Fase 0/1** (scaffold). Cada módulo declara en su docstring la fase en la que se implementa.
