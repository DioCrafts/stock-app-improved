# Arquitectura del backend — Equity Research Terminal

> Documento de arquitectura. Análisis basado **exclusivamente en el código fuente** del frontend
> (no documentación). Regla aplicada en todo el documento: **no se inventa nada**; lo que no es
> determinable desde el código se marca explícitamente como **"no determinable"** o **"a definir"**.

---

## 0. Resumen del análisis del frontend

He analizado todo el código fuente (no documentación): los 3 puntos de entrada, `App.jsx`, `data.js`,
los dos archivos de componentes y las 3 pantallas. Confirmo que **no existe ninguna capa de red** — la
búsqueda de `fetch / axios / http / websocket` no devuelve coincidencias reales (solo falsos positivos
como `capex` / `capitalize`). Todo se sirve desde el objeto `DATA` en `data.js` y el estado de usuario
vive en `localStorage`.

Archivos revisados:

- `index.html`, `src/main.jsx` — bootstrap.
- `src/App.jsx` — shell: sidebar nav, búsqueda global, theme, routing, índices de cabecera.
- `src/data.js` — dataset mock (`companies`, `byTicker`, `watchlist`, `YEARS`, generadores).
- `src/components/ui.jsx` — formatters, iconos, charts, scores.
- `src/components/shared.jsx` — celdas de tabla, score widgets, page header.
- `src/screens/WatchlistOverview.jsx` — `Watchlist` + `CompanyOverview`.
- `src/screens/ScreenerCompare.jsx` — `Screener` + `Compare`.
- `src/screens/ValuationFinancials.jsx` — `Valuation` (DCF) + `Financials`.

---

## 1. El "contrato" que la UI exige al backend (derivado del código)

El backend tiene una misión central: **producir el mismo objeto `company` que hoy fabrica `data.js`**,
más unos pocos extras. Campos que consume la UI:

| Grupo          | Campos exactos (de `data.js`)                                   | Dónde se pinta                          |
| -------------- | --------------------------------------------------------------- | --------------------------------------- |
| Identidad      | `ticker, name, sector, exchange, currency, employees, desc`     | Header ficha, search, monogramas        |
| Precio/mercado | `price, change, prevClose, marketCap, beta`                     | Watchlist, ficha, compare               |
| Valoración     | `pe, fwdPe, peg, pb, ps, evEbitda, divYield, fcfYield`          | Ficha (Valuation), Screener, Compare    |
| Rentabilidad   | `roe, roic, grossMargin, opMargin, netMargin`                   | Ficha (Profitability), Compare          |
| Crecimiento    | `revGrowth, epsGrowth`                                          | Ficha, Screener, Compare                |
| Salud/balance  | `debtEq, currentRatio`                                          | Ficha (Growth & risk), Compare          |
| Scores         | `scores.{value, growth, health, momentum, composite}`          | ScoreRing, ScoreBar, ScorePip, CompositeMini |
| Series         | `hist` (precios), `revenue` (6 años $B)                         | AreaChart, Sparkline, RevenueBars       |
| Constante      | `YEARS = [2020..2025]`                                          | Eje de Financials/Revenue               |

### Convenciones de unidades (determinables del código — críticas para que el backend "encaje")

- `marketCap`, `revenue`, FCF están en **miles de millones ($B)** → `fmt.cap` (`ui.jsx:11`) divide
  entre 1000 para mostrar "T".
- `change` es un **porcentaje** ya calculado (ej. `2.84` = +2.84 %).
- `divYield`, `roe`, márgenes, `revGrowth`, `epsGrowth` están en **puntos porcentuales**
  (ej. `roe: 91.2` = 91.2 %, `divYield: 2.9` = 2.9 %).
- Campos que pueden ser `null` (caso JPM en `data.js:159`): `evEbitda, roic, grossMargin, fcfYield,
  currentRatio` → el backend **debe poder emitir `null`** y la UI ya lo maneja ("—").
- `composite` **es determinable**: `value*0.35 + growth*0.30 + health*0.20 + momentum*0.15`
  (`data.js:48`).

### Hardcodeado hoy en el JSX (no en `data.js`) que el backend debería servir

- Índices de cabecera S&P / NASDAQ / VIX → valores literales en `App.jsx:186-188`.
- Estado "Market open" → literal en `App.jsx:175`.

### Cosas que la UI deriva en el cliente y que con yfinance pasarían a datos reales

- Los estados financieros (`buildStatements`, `ValuationFinancials.jsx:240`) hoy se **inventan** a
  partir de `revenue` + márgenes. Con yfinance vendrían reales.
- El DCF (`ValuationFinancials.jsx:67`) calcula en el cliente; solo necesita que el backend le dé los
  fundamentales base (FCF, net debt, shares vía `marketCap/price`).

---

## 2. Mapeo a yfinance (lo determinable vs lo que hay que definir)

| Campo UI                                                          | Origen en yfinance                                                                                                                  | Conversión necesaria                  |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `name, sector, exchange, currency, employees, desc, beta`        | `Ticker.info` (longName, sector, fullExchangeName, currency, fullTimeEmployees, longBusinessSummary, beta)                          | directa                               |
| `price, prevClose, marketCap`                                    | `info` (currentPrice, previousClose, marketCap)                                                                                    | `marketCap / 1e9` → $B                |
| `change`                                                         | calcular `(price/prevClose - 1) * 100`                                                                                             | a %                                   |
| `pe, fwdPe, peg, pb, ps, evEbitda, divYield`                     | `info` (trailingPE, forwardPE, pegRatio, priceToBook, priceToSalesTrailing12Months, enterpriseToEbitda, dividendYield)             | normalizar `divYield` a puntos %      |
| `roe, grossMargin, opMargin, netMargin, revGrowth, epsGrowth`    | `info` (returnOnEquity, grossMargins, operatingMargins, profitMargins, revenueGrowth, earningsGrowth)                              | `× 100` (yfinance da fracción)        |
| `debtEq, currentRatio`                                           | `info` (debtToEquity, currentRatio)                                                                                                | directa                               |
| `fcfYield`                                                       | `freeCashflow / marketCap × 100`                                                                                                   | derivado                              |
| `hist` (por rango 1M/3M/6M/1Y)                                   | `Ticker.history(period, interval)`                                                                                                 | serie de cierres                      |
| `revenue` (6 años) + statements                                  | `income_stmt`, `balance_sheet`, `cashflow` (anuales)                                                                               | $B                                    |
| Índices header                                                   | `Ticker("^GSPC" / "^IXIC" / "^VIX")`                                                                                               | —                                     |
| `roic`                                                           | **no hay campo directo** → calcular o `null`                                                                                       | **no determinable** la fórmula deseada |
| `scores.{value,growth,health,momentum}`                          | **no existen en yfinance**; en `data.js` son constantes mock                                                                       | **metodología no determinable** → definir |

---

## 3. Mercados y universo de tickers (US / Canadá / UK)

Requisito del producto: el universo es **todos los tickers de EE.UU., Canadá y Reino Unido** (no los 15
del mock). Esto introduce consideraciones que **no se derivan del código** y que cambian la arquitectura.

### 3.1 Lo que hay que tener claro

- **yfinance NO descubre tickers.** Solo descarga datos de un símbolo ya conocido. Por tanto, la
  **fuente del listado de símbolos por mercado es externa y a definir** (no determinable desde el código).
- Sufijos de símbolo que usa yfinance/Yahoo por mercado (convención conocida, no derivada del código):
  - **EE.UU.** (NYSE, NASDAQ, NYSE American): sin sufijo (ej. `AAPL`).
  - **Canadá**: TSX → sufijo `.TO` (ej. `SHOP.TO`); TSX Venture → `.V`.
  - **Reino Unido**: LSE → sufijo `.L` (ej. `HSBA.L`).
- **Fuentes candidatas del listado** (a confirmar/definir, no impuestas por el código):
  - EE.UU.: ficheros de símbolos de NASDAQ Trader (`nasdaqlisted` / `otherlisted`).
  - Canadá: directorio de emisores de TSX / TSXV.
  - UK: listado de instrumentos de LSE.
  - *Decisión abierta:* qué fuente concreta y bajo qué términos de uso. **A definir.**
- **Alcance del universo (a definir):** ¿solo acciones comunes, o también ETFs/fondos/ADRs? El código
  actual solo modela acciones; el alcance real es **no determinable** desde el código.

### 3.2 Implicaciones de escala (consecuencia directa de "todos los tickers")

El universo combinado es del orden de **miles a >10.000 símbolos**. Esto obliga a tres cambios respecto
al diseño original pensado para 15 tickers:

1. **Persistencia (SQLite).** No se puede recalcular en cada request. Se necesita una tabla con el
   *snapshot* de fundamentales de todo el universo para que el screener y la búsqueda consulten rápido.
   SQLite (un solo fichero, sin servidor) sigue siendo KISS.
2. **Ingesta batch programada.** Descargar `.info` de >10.000 tickers vía yfinance es lento y está
   sujeto a *rate limiting*. Se necesita un job periódico (p. ej. diario) que refresque el snapshot,
   en vez de llamar a yfinance en caliente por petición.
3. **Screener y search server-side.** Con miles de filas, el filtrado/orden/búsqueda dejan de poder
   hacerse en el cliente (como hoy con 15) y pasan a ser **consultas en el backend** con paginación.

> Riesgo operativo a tener en cuenta (factual, no del código): el *rate limiting* de Yahoo/yfinance y
> sus términos de uso son una restricción real a este volumen. Estrategia de refresco, reintentos y
> caché son parte del diseño, no un extra.

---

## 4. Estructura de repositorio propuesta (FastAPI, LLM-friendly + KISS)

> **Recomendación, no derivada del código:** framework **FastAPI + uvicorn** (estándar para envolver
> yfinance; validación con Pydantic = el "contrato" tipado que espeja `data.js`). Persistencia
> **SQLite** (un fichero, KISS) justificada por el universo grande. Scheduler **APScheduler** para la
> ingesta batch. Se coloca como carpeta `backend/` en este mismo repo (monorepo simple).

Principio LLM-friendly: **un archivo por área de la UI**, nombres explícitos, una sola dirección de
dependencias (`routers → services → {db, ingest, universe, cache}`), y `yfinance` aislado en un único
punto para poder cambiarlo/mockearlo sin tocar el resto.

```
stock-app-improved/
├── src/ ...                       # frontend React actual (la estructura de pantallas no cambia)
│
└── backend/
    ├── pyproject.toml             # deps: fastapi, uvicorn, yfinance, pydantic, pydantic-settings,
    │                              #       diskcache, apscheduler  (sqlite = stdlib)
    ├── .env.example               # PORT, CORS_ORIGIN, CACHE_TTL_SECONDS, DB_PATH, REFRESH_CRON
    ├── README.md
    │
    ├── app/
    │   ├── main.py                # crea FastAPI, CORS hacia Vite, monta routers, arranca scheduler
    │   ├── config.py              # settings (TTL caché, CORS, ruta DB, cron de refresco)
    │   │
    │   ├── models/                # Pydantic = contrato 1:1 con el objeto de data.js
    │   │   ├── company.py         # Company, Scores, Snapshot  ── espeja data.js campo a campo
    │   │   ├── price.py           # PricePoint, PriceSeries (hist por rango)
    │   │   ├── financials.py      # IncomeStatement, BalanceSheet, CashFlow, FinancialsBundle
    │   │   └── market.py          # IndexQuote, MarketStatus
    │   │
    │   ├── routers/               # endpoints — UN archivo por pantalla/área de UI
    │   │   ├── companies.py       # GET /companies, GET /companies/{ticker}
    │   │   ├── prices.py          # GET /companies/{ticker}/prices?range=1M|3M|6M|1Y
    │   │   ├── financials.py      # GET /companies/{ticker}/financials
    │   │   ├── screener.py        # GET /screener  (presets + filtros, server-side, paginado)
    │   │   ├── search.py          # GET /search?q=  (consulta el universo en DB)
    │   │   └── market.py          # GET /market/indices, GET /market/status
    │   │
    │   ├── services/              # lógica de negocio (orquesta ingest + scoring + db + caché)
    │   │   ├── company_service.py
    │   │   ├── financials_service.py
    │   │   ├── screener_service.py   # replica FILTER_DEFS / SCREEN_PRESETS del front (en SQL)
    │   │   └── scoring.py            # value/growth/health/momentum + composite
    │   │
    │   ├── universe/              # NUEVO: descubrimiento de tickers US / CA / UK
    │   │   ├── providers.py       # un provider por mercado (US, TSX/TSXV, LSE) → lista de símbolos
    │   │   ├── normalize.py       # normaliza a símbolo yfinance (sufijos .TO / .V / .L)
    │   │   └── refresh.py         # construye/actualiza la tabla `universe` en DB
    │   │
    │   ├── ingest/                # ÚNICO punto que conoce yfinance
    │   │   ├── yfinance_client.py # wrapper fino: .info, .history, .income_stmt... (+ reintentos)
    │   │   └── mappers.py         # yfinance → modelos Pydantic (+ conversiones de unidad)
    │   │
    │   ├── db/                    # NUEVO: persistencia (SQLite) — justificada por la escala
    │   │   ├── schema.py          # tablas: universe, company_snapshot
    │   │   └── queries.py         # consultas de screener / search / companies
    │   │
    │   ├── jobs/                  # NUEVO: ingesta batch programada
    │   │   └── refresh_snapshots.py  # refresca fundamentales de todo el universo (cron)
    │   │
    │   └── cache/
    │       └── store.py           # caché TTL en disco para prices/statements on-demand
    │
    └── tests/
        ├── test_mappers.py        # conversiones de unidad ($B, %, null)
        ├── test_scoring.py        # composite = 0.35/0.30/0.20/0.15
        ├── test_screener.py       # presets/filtros == comportamiento del front
        └── test_universe.py       # normalización de sufijos por mercado
```

### Trazabilidad componente UI → endpoint → archivo backend

| Componente UI (archivo actual)             | Endpoint                                | Archivos backend que lo sirven                         |
| ------------------------------------------ | --------------------------------------- | ------------------------------------------------------ |
| `GlobalSearch` (`App.jsx:28`)              | `GET /search?q=`                        | `routers/search.py` → `db/queries.py`                  |
| `IndexChip` header (`App.jsx:197`)         | `GET /market/indices`, `/market/status` | `routers/market.py` → `ingest`                         |
| `Watchlist` (`WatchlistOverview.jsx:13`)   | `GET /companies?tickers=`               | `routers/companies.py` → `company_service` + `scoring` |
| `CompanyOverview` (`WatchlistOverview.jsx:129`) | `GET /companies/{ticker}` + `/prices` | `routers/companies.py`, `routers/prices.py`            |
| `Screener` (`ScreenerCompare.jsx:33`)      | `GET /screener`                         | `routers/screener.py` → `screener_service` → `db`      |
| `Compare` (`ScreenerCompare.jsx:214`)      | `GET /companies?tickers=`               | `routers/companies.py`                                 |
| `Valuation` (DCF) (`ValuationFinancials.jsx:47`) | `GET /companies/{ticker}` (base)   | `routers/companies.py` (cálculo DCF se queda en cliente, KISS) |
| `Financials` (`ValuationFinancials.jsx:287`) | `GET /companies/{ticker}/financials`  | `routers/financials.py` → `financials_service`         |

### Cómo se conecta el frontend

`src/data.js` deja de fabricar datos y pasa a una capa `src/api.js` (un `fetch` por endpoint) — las
pantallas no cambian su estructura, solo el origen de `DATA`. La watchlist y el compare-set pueden
**seguir en `localStorage`** (KISS, sin auth, como hoy) o migrar a `/watchlist` si más adelante se
quiere multi-dispositivo.

---

## 5. No determinable / decisiones abiertas

- **Metodología de los scores `value/growth/health/momentum`**: en el código son constantes mock
  arbitrarias (`data.js:67` etc.). La fórmula real **no es determinable** — queda como
  `services/scoring.py` a definir. El `composite` sí es determinable.
- **`roic` real**: yfinance no lo expone directo → fórmula de cálculo **no determinable**.
- **Mapeo exacto de cada fila de los estados financieros** → **RESUELTO** en Fase 1 (verificado en vivo,
  ver §7.7); las etiquetas reales de yfinance están confirmadas. El cálculo/relleno se hace en Fase 6.
- **Estado de mercado open/closed**: yfinance lo da de forma irregular (`marketState`) → **parcialmente
  determinable**.
- **Fuente del listado de tickers** por mercado (US/CA/UK) y **alcance** (acciones vs ETFs/fondos):
  **a definir** (no determinable desde el código).
- **Persistencia**: se propone **SQLite** (justificada por el universo grande). Auth y watchlists por
  usuario quedarían como ampliación futura (no hay nada de eso en el código).
- **Monorepo vs repo separado** y **framework** (FastAPI vs Flask): elecciones del equipo; arriba va la
  recomendación por defecto, no algo impuesto por el código.

---

## 6. Roadmap — tareas desde ahora hasta el producto terminado

> Leyenda: **[D]** = a definir / no determinable desde el código (requiere decisión). Las fases son
> incrementales; cada una deja algo verificable.

### Fase 0 — Decisiones y arranque  ✅ COMPLETADA (ver §7)
- [x] Stack: **uv + FastAPI + Python 3.12** (3.12 fijado: FinanceDatabase exige ≤3.13), monorepo (`backend/`), persistencia SQLite, scheduler APScheduler.
- [x] Alcance del universo: **equities** (acciones), excluyendo ETFs/fondos/warrants/units/rights/preferreds (recomendado — el contrato de la UI son fundamentales de empresa operativa). Pendiente confirmación del usuario.
- [x] Fuentes de tickers US/CA/UK investigadas y elegidas (ver §7). Base: **FinanceDatabase** (MIT); overlays oficiales gratuitos por mercado.
- [x] `backend/` creado: `pyproject.toml`, `.venv` (uv), deps, `.env.example`, `README.md`, `.gitignore`.
- [x] Tooling: `ruff` + `pytest` configurados; `uv sync` y `uv run pytest` (3 tests) en verde.
- [ ] Acordar el contrato de API (OpenAPI) con el frontend antes de implementar (esqueleto montado; rutas en Fase 6).

### Fase 1 — Modelos / contrato (Pydantic = espejo de `data.js`)  ✅ COMPLETADA
- [x] `models/company.py` (Company, Scores) con tipos y `null` donde aplica (`scores` opcional hasta Fase 5).
- [x] `models/price.py` (PricePoint, PriceSeries con `range` literal), `models/financials.py`
      (IncomeYear/BalanceYear/CashFlowYear/FinancialsBundle, claves 1:1 con el front), `models/market.py`
      (IndexQuote, MarketStatus).
- [x] Conversiones de unidad documentadas y centralizadas en `ingest/mappers.py` (ver §7.7).
- [x] `tests/test_models.py`. Total **13 tests** en verde; `ruff` limpio.

### Fase 2 — Universo de tickers (US / CA / UK)  ✅ COMPLETADA (núcleo)
- [x] `universe/providers.py`: carga **FinanceDatabase** (`fd.Equities()`) filtrada por exchange US/CA/UK.
- [x] `universe/normalize.py`: mapa exchange→mercado + normalización US `.`→`-`.
- [x] `db/schema.py` + `db/queries.py` (SQLite stdlib) + `universe/refresh.py`: tabla `universe` poblada
      → **13.844 acciones** (US 9.296 · CA 2.888 · UK 1.660). Ejecutar: `uv run python -m app.universe.refresh`.
- [x] Solo acciones; UK filtrado a empresas británicas (GBP) — ver §7.2.
- [ ] (Opcional, frescura) overlays oficiales: NASDAQ Trader (US), TMX Excel (CA), LSE Excel (UK).
- [x] `tests/test_universe.py` (total **7 tests** en verde).

### Fase 3 — Ingesta yfinance  ✅ COMPLETADA (núcleo)
- [x] `ingest/yfinance_client.py`: wrapper fino (`.info`, `.income_stmt`, `.history`) con reintentos + caché.
- [x] `ingest/mappers.py`: yfinance → `Company` con conversiones de unidad verificadas (ver §7.7) y `None` en faltantes.
- [x] `cache/store.py`: caché TTL en disco (`diskcache`).
- [x] `services/company_service.build_company(symbol)`: builder en vivo, validado con AAPL / SHOP.TO / HSBA.L.
- [x] `tests/test_mappers.py` (deterministas, sin red). Total **10 tests** en verde.
- [ ] Mapear `.history` a un `PriceSeries` por rango (queda con el endpoint `/prices`, Fase 6).

### Fase 4 — Persistencia + ingesta batch  ✅ COMPLETADA (núcleo)
- [x] `db/schema.py`: tabla `company_snapshot` (columnas indexables del screener + blob JSON del Company).
- [x] `db/queries.py`: `upsert_snapshots`/`get_snapshot`/`count_snapshots`/`snapshot_symbols` (resumibilidad) + `universe_rows`.
- [x] `jobs/refresh_snapshots.py`: job **resumible** (`only_missing`), tolerante a fallos (status `error`), con
      pausas y escritura por lotes. CLI `--limit/--all/--pause`. Smoke test **15/15 OK**.
- [x] Scheduler en **proceso dedicado** (`app/jobs/scheduler.py`, BlockingScheduler), NUNCA en el web (H2):
      cron `REFRESH_CRON` → universo → snapshots (refresco por antigüedad `REFRESH_MAX_AGE_HOURS`) → scores.
      `max_instances=1` + `coalesce` + `misfire_grace_time=3600` (M7). Frescura diaria resuelta.
- [x] Refresco por antigüedad (`refresh_snapshots(max_age_hours=…)` / `--max-age-hours`) + **WAL** en SQLite
      (API lee y job escribe sin bloqueos).
- [~] Ingesta COMPLETA (~13.790): **lanzada en background** (resumible; ~horas por rate-limit de Yahoo).
- [x] (Calidad) filtro de ETPs/ETFs aplicado en `universe/providers.is_fund_like` — ver §7.2.

### Fase 5 — Scoring  ✅ COMPLETADA
- [x] `services/scoring.py`: percentiles **por mercado** con los factores aprobados + composite renormalizado. Ver §7.8.
- [x] Momentum capturado en la ingesta (`ret_1y` = 52WeekChange, `px_vs_200d` = precio/200dMA − 1).
- [x] `jobs/score_snapshots.py`: pasada que escribe `score_*` + embebe los scores en el Company.
      CLI: `uv run python -m app.jobs.score_snapshots` (ejecutar DESPUÉS de la ingesta).
- [x] `tests/test_scoring.py` (percentiles, inversión value, normalización por mercado, renorm composite). Total **28 tests**.
- [ ] (Refinamiento opcional) exigir un mínimo de pilares para el composite — ver caveat en §7.8.

### Fase 6 — Endpoints (routers + services)  ✅ COMPLETADA
- [x] `companies.py`: `GET /companies` (lista/por `?tickers=`) y `GET /companies/{ticker}` (snapshot o fallback en vivo).
- [x] `prices.py`: `GET /companies/{ticker}/prices?range=1M|3M|6M|1Y` (conversión GBp→£ aplicada).
- [x] `financials.py`: `GET /companies/{ticker}/financials` (income/balance/cashflow; bancos → líneas None OK).
- [x] `screener.py`: `GET /screener` server-side + paginación (filtros = FILTER_DEFS; presets se resuelven en el front).
- [x] `search.py`: `GET /search?q=` sobre el universo (join con snapshot para price/composite).
- [x] `market.py`: `GET /market/indices` y `GET /market/status`.
- [x] CORS, errores 404/validación, paginación. **Smoke real de todos los endpoints OK.**
- [x] `tests/test_screener.py` + `tests/test_financials.py`. Total **24 tests** en verde; `ruff` limpio.

### Fase 7 — Integración del frontend  ✅ COMPLETADA
- [x] `src/api.js`: cliente `fetch` por endpoint + hook `useAsync` + `VITE_API_URL` (default :8000).
- [x] `DATA`/`data.js` desconectado de las 3 pantallas + shell (el fichero queda muerto, se puede borrar).
- [x] Estados **loading / error / empty** (`Loading`/`ErrorBox`/`Empty` en `shared.jsx`); score widgets tolerantes a `null`.
- [x] `GlobalSearch` → `/search` con debounce (server-side).
- [x] `Screener` → `/screener` server-side (sin filtrado en cliente, paginado); `Compare`/`CompanyPicker` con búsqueda (`/search`) en vez del universo completo.
- [x] Índices de cabecera y "Market open" desde `/market/*`; precios de la ficha desde `/companies/{t}/prices`.
- [x] Watchlist/compare siguen en `localStorage` (semilla `DEFAULT_WATCH`).
- [x] Verificado: `npm run build` OK (22 módulos); backend + CORS + Vite dev server sirviendo y `api.js` apuntando al backend. (Render visual en navegador: pendiente de confirmación manual.)

### Fase 8 — Calidad y robustez
- [x] **Seguridad (auditoría M1–M4):** validación estricta de `ticker` (`app/validation.py`, M1) +
      cota de fan-out por request + rate-limit `limit_req` en nginx (M2) + contenedores **no-root**
      (uid 1001, M3) + cabeceras de seguridad/gzip/`client_max_body_size` en nginx (M4). Verificado en Docker.
- [ ] Tests de integración de endpoints con yfinance mockeado.
- [ ] Manejo end-to-end de errores, timeouts y fallback cuando yfinance falla.
- [ ] Lint + typecheck (backend y frontend).
- [x] **Rendimiento (M5/M6/L6):** `ORDER BY` con `col IS NOT NULL` en vez de `col IS NULL, col`
      (EXPLAIN confirma `SEARCH ... USING INDEX`, sin temp B-TREE) + índices para todas las columnas de
      orden/filtro + batch en watchlist/compare (1 conexión + 1 query). Pendiente: FTS5 para search (L7).
- [x] **Datos (M11/M12):** `financialCurrency` en el contrato + conversión FX (yfinance `{a}{b}=X`) de los
      estados financieros (siempre en vivo → arreglado ya) y de `revenue` para DCF/gráficos. Los snapshots
      ya guardados rellenan `financialCurrency` al re-ingerir o en el refresco diario del scheduler.
- [x] **Scoring robusto (M13/M14):** cobertura mínima por pilar (los anchos exigen ≥2 factores) + n mínimo
      por percentil (10) + composite exige ≥2 pilares. `with_composite` 10.289 → 9.665 (descarta composites
      poco fiables).
- [x] **DCF (M15):** guarda de Gordon (`r − g ≤ 0.5%` → fair value `—`), evita valores absurdos/∞ en la
      rejilla de sensibilidad.
- [x] **Ops (M8/M9/M10):** caché TTL en el volumen persistente (`CACHE_DIR=/data/cache`, M8) + timeouts de
      nginx para `/financials` (M9) + límites de memoria/CPU en compose (M10). Verificado en Docker.
- [x] **Lows (L1–L3, L7, L13, L15, L16, L18–L22, L24):** dedup de `revenue` por año (L1), `0.0`≠`None` en
      peg/fcfYield (L2), **FTS5** en `/search` (L3/L7), `useAsync` sin parpadeo en refetch (L13), guards de
      NaN en FcfBars (L15), `gainers/decliners` correctos (L16), pin `yfinance>=1.4,<2` (L18), `slice(-5)`
      en Compare (L19/L20), normalización de barra en `api.js` (L21), clamp de scores en widgets (L22),
      FCF margin/Capex-rev sobre el último año con ambos datos (L24). 46 tests; ruff limpio.

### Fase 9 — Despliegue y operación  ✅ COMPLETADA (núcleo)
- [x] `backend/Dockerfile` (uv + Python 3.12) + `Dockerfile` frontend (build Vite → Nginx) + `docker-compose.yml`
      (backend + frontend + volumen SQLite `dbdata`). Ambas imágenes **construyen y arrancan** (verificado).
- [x] Nginx sirve la SPA y **proxya `/api` → backend** (mismo origen, sin CORS en prod). `api.js` soporta API relativa.
- [x] Scheduler como **servicio aparte** en compose (`scheduler`, misma imagen+volumen que `backend`): el web solo sirve la API (H2 resuelto; sin riesgo multi-worker).
- [x] Health check (compose) + endpoints sanos con DB vacía.
- **Fix de despliegue (hallado al verificar):** `init_db` ahora se ejecuta al arrancar la app → con volumen nuevo
  los endpoints devuelven vacío (200) en vez de 500. El bootstrap de datos requiere **orden**:
  `app.universe.refresh` → `app.jobs.refresh_snapshots` → `app.jobs.score_snapshots` (documentado en compose).
- [ ] Pinear versión de la imagen `uv`, logging estructurado y CI — endurecimiento (Fase 8).

### Fase 10 — Ampliaciones futuras (opcionales)
- [ ] Auth + watchlists por usuario (multi-dispositivo).
- [ ] DCF como endpoint (`POST /valuation/dcf`) si se quiere centralizar el cálculo.
- [ ] Precios en vivo (WebSocket) — hoy precio y "Market open" son estáticos.
- [ ] `roic` real y mapeo fino de líneas de los estados financieros.

---

## 7. Fase 0 — Decisiones cerradas e investigación de fuentes (2026-06-05)

> Esta sección cierra los puntos **[D]** que estaban abiertos. La investigación de fuentes se hizo
> contra fuentes en vivo; donde algo no se pudo verificar se marca **"no verificable"**.

### 7.1 Stack (decidido)
- **uv + FastAPI + Python 3.12.** Python se fija en **3.12** porque `FinanceDatabase` (la fuente del
  universo) **no instala su versión actual en Python 3.14** (su dependencia `financetoolkit` no tiene
  wheel para 3.14 y caería a una versión antigua incompleta). uv gestiona el 3.12 sin tocar el sistema.
- **Persistencia SQLite**, **scheduler APScheduler 3.x**, caché en disco `diskcache`.
- `backend/` creado y verificado: `uv sync` OK, `uv run pytest` → 3 tests en verde, `/health` responde.

### 7.2 Alcance del universo (DECIDIDO: solo acciones; UK solo empresas británicas)
- **Solo acciones** (confirmado por el usuario): se usa `fd.Equities()` (los ETFs/fondos viven en
  clases aparte de FinanceDatabase, así que quedan excluidos por construcción). Motivo: toda la UI
  (P/E, ROE, márgenes, DCF, estados financieros) son fundamentales que **no aplican a ETFs/fondos**.
- **UK solo empresas británicas (GBP)** (confirmado por el usuario): al inspeccionar los datos reales,
  el universo UK traía **2.025 cross-listings extranjeros** (Akzo Nobel, Neoen… en EUR/USD/CHF, 764 vía
  IOB `.IL`). Se filtran y se conservan solo las cotizadas en GBP. US y CA estaban limpios (USD/CAD) y
  no se tocan. Flag en `.env`: `UK_GBP_ONLY=true`.
- **Tamaño real medido** (refresco 2026-06-05, FinanceDatabase → SQLite):
  **US 9.296 · CA 2.888 · UK 1.660 = 13.844 acciones** (cifras vivas, varían con el dataset).
- **Contaminación ETP/ETF — RESUELTA:** `fd.Equities()` incluía productos cotizados etiquetados como
  equity (ETPs apalancados Leverage Shares/GraniteShares en LSE; ETFs cripto en US). Filtro de **alta
  precisión** por nombre (` ETF`/` ETC`/` ETP`/` ETN`/"Leverage Shares"/"GraniteShares") aplicado en
  `universe/providers.is_fund_like` (sin falsos positivos: "American Vanguard" se conserva). Eliminó **54**
  entradas → universo **13.790** (US 9.273 · CA 2.888 · UK 1.629).

### 7.3 Fuentes de tickers (decidido: FinanceDatabase + overlays oficiales)

**Fuente base única (KISS): `FinanceDatabase`** (MIT). Cubre los 3 mercados en un solo paquete y sus
símbolos son directamente usables por yfinance **al filtrar por `exchange` (no por `country`)**:

| Mercado | Códigos de exchange en FinanceDatabase |
| ------- | -------------------------------------- |
| US      | `NYQ` (NYSE), `NMS`/`NGM`/`NCM` (NASDAQ), `ASE` (NYSE American) |
| CA      | `TOR` (TSX), `VAN` (TSXV), `CNQ` (CSE), `NEO` (Cboe Canada) |
| UK      | `LSE`, `IOB`, `AQS` (Aquis) |

> Limitación conocida: FinanceDatabase es **estático y ~2 años desactualizado** (último release 2024-06).

**Overlays oficiales gratuitos** (opcionales, para frescura por mercado — todos verificados en vivo):

| Mercado | Fuente oficial gratuita | Formato / cadencia | Notas clave |
| ------- | ----------------------- | ------------------ | ----------- |
| **US** | NASDAQ Trader: `nasdaqlisted.txt` + `otherlisted.txt` (`nasdaqtrader.com/dynamic/SymDir/`) | pipe-delimited, intradía/diario | Filtrar `ETF=N` y `Test Issue=N`; descartar la última línea `File Creation Time`. |
| **CA** | TMX "TSX & TSXV Listed Issuers" Excel (vía `tsx.com/en/listings/current-market-statistics`) | XLSX, mensual | Columnas `Root Ticker` + `Exchange`. © TSX: **no redistribuir el fichero**. |
| **UK** | LSE Reports "List of all companies" / DTI (`londonstockexchange.com/reports`) | XLSX, mensual/diario | Columna `TIDM`. Página JS (no `curl` directo). |

### 7.4 Convenciones de símbolo → yfinance (confirmadas)
- **US**: sin sufijo. Clases de acción: `.` → `-` (ej. `BRK.B` → `BRK-B`).
- **CA**: TSX `.TO` · TSXV `.V` · CSE `.CN` · Cboe Canada `.NE`. El `.` interno → `-`
  (ej. `BCE.PR.B` → `BCE-PR-B.TO`, `BEP.UN` → `BEP-UN.TO`, CPC `FIVD.P` → `FIVD-P.V`).
- **UK**: sufijo `.L`. El `.` del TIDM → `-` (ej. `BT.A` → `BT-A.L`). **Precios en GBp (peniques):
  dividir por 100 cuando `currency == "GBp"`** (si no, todo sale ×100). `financialCurrency` puede ser GBP.
- En los 3 mercados: **no todos los símbolos resuelven en Yahoo** → validar con yfinance y descartar fallos.

### 7.5 Licencias / términos (factual, a tener en cuenta)
- **FinanceDatabase / pytickersymbols**: MIT (libres).
- **NASDAQ Trader**: declarado "sin restricción"; sin licencia formal CC → términos exactos de
  redistribución **no verificable**.
- **TMX Excel**: © TSX Inc. — uso interno OK, **prohibido redistribuir/revender el fichero**.
- **LSE Excel**: gratuito para uso interno; redistribución/uso comercial restringido (ruta programática
  oficial = LSE Data Shop, de pago).
- **Yahoo / yfinance**: no oficial, **solo uso personal**, con rate-limit; no redistribuir sus datos.
- Implicación: usar estas listas como **input interno** del pipeline es uso normal; **no republicar** los
  ficheros oficiales ni los datos de Yahoo.

### 7.6 Riesgo confirmado
El **rate-limit de Yahoo** con ~9.000–12.000 tickers es real → refuerza la necesidad del **job batch
con lotes y pausas** (Fase 4) y de la caché. `pytickersymbols` se descartó como fuente principal: solo
trae constituyentes de índices y **no cubre Canadá**.

### 7.7 Conversiones de unidad yfinance → contrato (VERIFICADO en vivo, Fase 3)
Medido contra **yfinance 1.4.1** con AAPL / SHOP.TO / HSBA.L. Corrige suposiciones de §2:

| Campo contrato | Campo yfinance | Regla CONFIRMADA |
| --- | --- | --- |
| `marketCap`, `fcfYield` base, `revenue` | `marketCap`, `freeCashflow`, `Total Revenue` | **÷ 1e9** → $B |
| `roe`, `grossMargin`, `opMargin`, `netMargin`, `revGrowth`, `epsGrowth` | `returnOnEquity`, `*Margins`, `revenueGrowth`, `earningsGrowth` | **× 100** (vienen en fracción) |
| `divYield` | `dividendYield` | **NO se multiplica** — ya viene en puntos % (AAPL 0.35, HSBA 4.07). *(Corrige §2.)* |
| `debtEq` | `debtToEquity` | **÷ 100** — viene en porcentaje (AAPL 79.5 → 0.795). *(Detalle nuevo.)* |
| `change` | — | calcular `(price/prevClose − 1) × 100` |
| `fcfYield` | `freeCashflow / marketCap` | `× 100` |
| `peg` | `trailingPegRatio` (fallback `pegRatio`) | directa |
| `pe, fwdPe, pb, ps, evEbitda, beta, currentRatio` | homónimos | directa |
| `roic` | — | **None** (no existe campo; no determinable) |

**UK / GBp (HSBA.L):** `currency == "GBp"` ⇒ `price`/`prevClose` en **peniques → ÷ 100** a libras (y se
reporta `currency = "GBP"`). **`marketCap` ya viene en GBP (libras)**, así que solo `÷ 1e9`.
Verificado: marketCap ÷ (price÷100) = 17,15 B acciones ≈ las ~17,3 B reales de HSBC.

**Wrinkle cross-divisa (a abordar en Fase 6):** para SHOP.TO/HSBA.L el `financialCurrency` es USD
mientras el precio/marketCap están en CAD/GBP. Por eso `revenue` sale en **USD** aunque el precio esté
en otra divisa (HSBA: rev `[53.7, 64.5, 67.4, 66.2]` $B USD). Aceptable ahora; a normalizar en Financials.

**`income_stmt`:** columnas newest-first y el periodo más antiguo suele venir **NaN** → se filtra NaN y se
invierte a oldest→newest. yfinance gratis da ~4 años anuales (no 6 como el mock).

**Líneas de estados financieros confirmadas (Fase 1)** — clave del front → etiqueta yfinance:
- income: `revenue`→Total Revenue · `cogs`→Cost Of Revenue · `grossProfit`→Gross Profit ·
  `opex`→Operating Expense · `opInc`→Operating Income · `netInc`→Net Income · `eps`→Diluted EPS.
- balance: `cash`→Cash And Cash Equivalents · `assets`→Total Assets · `debt`→Total Debt ·
  `liab`→Total Liabilities Net Minority Interest · `equity`→Stockholders Equity.
- cashflow: `opCF`→Operating Cash Flow · `capex`→Capital Expenditure · `fcf`→Free Cash Flow.
- Importes ÷1e9 ($B) salvo `eps`. Campos ausentes (bancos sin Gross Profit/COGS) → None.

**`.history`:** columnas `Open/High/Low/Close/Volume/...`, índice de fechas (tz). El `Close` de UK viene en
**peniques** (HSBA.L 1360.8) → el mapper de `/prices` aplicará ÷100 igual que en `Company`.

### 7.8 Metodología de scoring (aprobada 2026-06-06)
Scoring por **percentiles dentro de cada mercado** (US/CA/UK por separado). Cada factor → percentil 0–100
(midrank); los "menor es mejor" se invierten. Pilar = media de los percentiles de sus factores disponibles
(falta de dato = se omite). Implementado en `services/scoring.py` (puro) + `jobs/score_snapshots.py` (DB).

| Pilar (peso) | Factores (↓ invertido) |
| --- | --- |
| Value (0.35) | pe↓ fwdPe↓ pb↓ ps↓ evEbitda↓ peg↓ fcfYield↑ divYield↑ |
| Growth (0.30) | revGrowth↑ epsGrowth↑ |
| Health (0.20) | roe↑ netMargin↑ opMargin↑ debtEq↓ currentRatio↑ |
| Momentum (0.15) | ret_1y↑ (52WeekChange) · px_vs_200d↑ |
| Composite | mezcla ponderada (pesos de data.js); **renormaliza** si falta algún pilar |

- **Inputs de momentum** se capturan en la ingesta (`ret_1y`, `px_vs_200d`) desde `.info` (sin descargas extra).
- **Limpieza:** ratios de valoración no positivos (pérdidas) → ignorados. Percentiles robustos a outliers
  (sin winsorizar). Pilar/score sin datos → `None` (la UI pinta "—").
- **Caveat — RESUELTO (M13/M14):** se exige cobertura mínima por pilar (anchos ≥2 factores), n≥10 por
  percentil y ≥2 pilares para el composite, de modo que una empresa con pocos datos ya no puntúa alto;
  los casos no fiables quedan en `None` ("—").
- **Nota:** los percentiles son significativos sobre el **universo completo**; con solo una muestra ingerida
  son ilustrativos. Ejecutar scoring tras la ingesta completa.
