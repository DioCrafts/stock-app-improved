# Informe de Auditoría de Código — stock-app-improved

> Auditoría adversarial de correctitud, seguridad, rendimiento/escala, contrato frontend, correctitud de datos y operaciones/despliegue. Todos los hallazgos listados han sido verificados.

## Resumen ejecutivo

### Conteo por severidad (tras deduplicar solapamientos)

| Severidad | Nº hallazgos |
|-----------|:---:|
| Critical  | 0 |
| High      | 2 |
| Medium    | 13 |
| Low       | 21 |
| **Total** | **36** |

> Nota: la lista original contenía 42 entradas; tras fusionar duplicados entre dimensiones (mismo problema reportado dos veces) quedan 36 hallazgos únicos. Ver detalle de fusiones en "Notas y límites".

### Conclusiones clave

1. **No hay vulnerabilidades críticas ni RCE directo**, pero sí dos problemas de alta severidad de arquitectura/correctitud que afectan al objetivo central del producto (mantener actualizados ~14k tickers): el backfill por defecto nunca reintenta los errores transitorios de Yahoo, y el job pesado de ingesta corre dentro del proceso web.

2. **El pipeline de ingesta no es robusto frente a cortes de Yahoo.** La promesa de resumibilidad del backfill está rota (los `status='error'` se tratan como "hechos") y el scheduler embebido no tiene control de misfire ni aislamiento multi-worker. Para un universo de 14k tickers que tarda horas, esto significa cobertura incompleta y silenciosa.

3. **Rendimiento de las consultas degradado de raíz.** El patrón `ORDER BY col IS NULL, col` invalida todos los índices del screener y del listado (full scan + temp B-TREE en cada request), y la búsqueda global usa `LIKE '%q%'` (full scan por pulsación). Los índices existentes no aportan nada con las queries actuales.

4. **Postura de seguridad de "desarrollo" desplegada como si fuera producción.** Falta validación del `ticker` que fluye a yfinance, no hay autenticación ni rate limiting (con amplificación 1→N hacia Yahoo), contenedor como root, nginx sin cabeceras de seguridad ni límites de tamaño/tasa, y CORS con comodines. Ninguno es crítico aislado, pero juntos dejan el servicio expuesto a abuso/DoS y baneo de Yahoo.

5. **Riesgo de correctitud de datos por mezcla de divisas.** `revenue` (financialCurrency) se combina sin etiqueta con `marketCap`/`price`/`fcfYield` (divisa de cotización) tanto en backend como en el DCF/ratios del frontend, produciendo cifras erróneas para empresas UK/CA sin aviso. El scoring también amplifica ruido con grupos pequeños y pilares de un solo factor.

6. **Operaciones sin red de seguridad.** Cache en disco efímera (se pierde en cada deploy → ráfaga a Yahoo), sin límites de memoria/CPU en compose, timeouts de nginx que cortan `/financials` en frío, y dependencia frontend→backend sin espera a healthy. Mitigable con cambios localizados y de bajo riesgo.

---

## Hallazgos por severidad

### High

#### H1. El backfill por defecto (`only_missing`) marca como "hecho" las filas con `status='error'` y nunca las reintenta
- **Ubicación:** `backend/app/jobs/refresh_snapshots.py:100-104` + `backend/app/db/queries.py:74-80` (`snapshot_symbols`)
- **Dimensión:** backend-correctness
- **Por qué importa:** En modo por defecto, `done = queries.snapshot_symbols(conn)` devuelve TODOS los símbolos en `company_snapshot`, incluidos los `status='error'`. Cualquier ticker que falló por un corte transitorio (timeout, rate-limit) queda excluido permanentemente del backfill; re-ejecutar el job nunca lo reintenta. La promesa de resumibilidad del docstring solo se cumple para símbolos sin NINGUNA fila.
- **Fix:** Considerar "hecho" solo lo que está OK: `done = queries.snapshot_symbols(conn, status='ok')` (la función ya acepta `status`). Así los errores se reintentan en la siguiente pasada. Para `max_age_hours` ya se usa `fresh_symbols` con `status='ok'`, que es correcto.

#### H2. El scheduler ejecuta el job pesado (universo + ingesta ~14k tickers + scoring) DENTRO del proceso web
- **Ubicación:** `backend/app/main.py:41-49` (`lifespan()` `scheduled_refresh` + `BackgroundScheduler`)
- **Dimensión:** performance-scale
- **Por qué importa:** Con `enable_scheduler=True`, `refresh_universe()` + `refresh_snapshots()` + `score_universe()` corren en un hilo del scheduler dentro del mismo uvicorn que sirve la API. `refresh_snapshots` recorre ~14k tickers con `pause=0.7s` (≈2,7h solo de pausas + red), con llamadas bloqueantes que compiten por CPU/GIL y por la DB con las peticiones HTTP. Con varios workers, cada worker arranca su PROPIO scheduler (N× la carga sobre Yahoo y la DB).
- **Fix:** Sacar el job del proceso web: ejecutarlo como contenedor/proceso aparte (cron del SO o worker dedicado) que invoque `python -m app.jobs.refresh_snapshots`. Si debe vivir dentro, usar un único worker y/o un lock entre procesos; documentar que `enable_scheduler` es incompatible con multi-worker.

---

### Medium

#### M1. Ticker sin validar fluye a la URL de yfinance (path-traversal / manipulación de request sobre el upstream + amplificación)
- **Ubicación:** `backend/app/routers/companies.py:30-34` (también `prices.py:16`, `financials.py:16`); `company_service.build_company/build_price_series`; `yfinance_client.get_info/get_history`
- **Dimensión:** security
- **Por qué importa:** El path param `ticker` se acepta solo con `.upper()` y se inyecta en la URL de yfinance vía f-string sin url-encode (`.../{symbol}` en quote.py:596, `.../chart/{ticker}` en history.py:208). Valores como `AAPL/../../v8/...` o con `?`/`#`/`@` manipulan ruta/query hacia query2.finance.yahoo.com. El host queda anclado a Yahoo (no SSRF arbitrario), pero no hay tope de longitud ni filtro; cada request entrante dispara varias salientes (amplificación, abuso de rate-limit).
- **Fix:** Validar con patrón estricto en el router/modelo, p.ej. `Annotated[str, Path(pattern=r'^[A-Z0-9.\-]{1,12}$')]`, rechazando `/`, `?`, `#`, `@`, espacios y longitudes excesivas, en `companies/{ticker}`, `prices` y `financials`. (Resuelve también la reflexión de entrada del hallazgo L17.)

#### M2. API pública sin autenticación ni rate limiting, con amplificación a yfinance (DoS)
- **Ubicación:** `backend/app/main.py:55-74`; routers companies/prices/financials/search
- **Dimensión:** security
- **Por qué importa:** Ningún endpoint exige auth ni hay rate limiting (ni en FastAPI ni en nginx). Endpoints que hacen llamadas en vivo a yfinance sin snapshot permiten pedir miles de tickers distintos (la caché TTL no ayuda: cada clave es nueva) y saturar el backend y/o provocar el baneo de Yahoo.
- **Fix:** Añadir rate limiting (slowapi o `limit_req` en nginx por IP) y limitar el fan-out en vivo: servir solo desde snapshot o cachear también los misses; opcionalmente API key. Como mínimo, `limit_req_zone` + `limit_req` en nginx para `/api/`.

#### M3. Contenedor backend corre como root
- **Ubicación:** `backend/Dockerfile` (todo el fichero; no hay directiva `USER`)
- **Dimensión:** security / deploy-ops *(fusión de dos hallazgos)*
- **Por qué importa:** uvicorn (que ejecuta yfinance, escribe SQLite y lanza jobs con `ENABLE_SCHEDULER=true`) corre como UID 0. Cualquier RCE/SSRF/escape escala a root; los ficheros del volumen `/data` (`app.db`, WAL, SHM) y `/app/.cache` quedan en propiedad de root, complicando backups/rotación.
- **Fix:** Antes del `CMD`: `RUN adduser --system --uid 1001 appuser && mkdir -p /data /app/.cache && chown -R appuser /data /app/.cache` y `USER appuser`. Asegurar que el volumen `dbdata` y el dir de cache sean escribibles por ese UID.

#### M4. nginx sin cabeceras de seguridad, sin gzip ni límite de tamaño de petición
- **Ubicación:** `nginx.conf:1-21` (`server`, `location /`, `location /api/`)
- **Dimensión:** security / deploy-ops *(fusión de dos hallazgos)*
- **Por qué importa:** Sin cabeceras de seguridad (X-Content-Type-Options, X-Frame-Options/CSP, Referrer-Policy) la SPA queda servible en iframes (clickjacking) y expuesta a MIME-sniffing. Sin `client_max_body_size`/`limit_req` el proxy `/api/` no limita tamaño ni tasa hacia el backend. Sin gzip se transfiere el bundle JS/CSS y JSON del screener sin comprimir; los estáticos hasheados de Vite no llevan `Cache-Control` inmutable.
- **Fix:** Añadir `add_header X-Content-Type-Options nosniff; add_header X-Frame-Options DENY; add_header Referrer-Policy no-referrer;` y una CSP básica; `client_max_body_size 1m;` y `limit_req` por zona para `/api/`; `gzip on; gzip_types application/javascript application/json text/css; gzip_min_length 1024;`; y `location ~* \.(js|css|woff2)$ { expires 1y; add_header Cache-Control "public, immutable"; }`.

#### M5. `ORDER BY "col IS NULL, col"` anula TODOS los índices del screener/listado (full scan + temp B-TREE sobre ~13k filas por request)
- **Ubicación:** `backend/app/db/queries.py:182-186` (`screen()`) y `120-124` (`list_company_data()`)
- **Dimensión:** performance-scale
- **Por qué importa:** La primera clave de orden es la EXPRESIÓN `col IS NULL`, no la columna, por lo que ningún índice es usable. Verificado con `EXPLAIN QUERY PLAN`: incluso para columnas indexadas el plan es `SCAN company_snapshot` + `USE TEMP B-TREE FOR ORDER BY`. Cada carga del screener/listado materializa y ordena ~13k filas (más el COUNT, otro scan) aunque devuelva 50. Los índices `idx_snap_composite`/`idx_snap_marketcap` no aportan nada.
- **Fix:** No anteponer `IS NULL`. Para empujar NULLs al final con índice: añadir `WHERE {col} IS NOT NULL` al ordenar por esa columna (los NULL ya se filtran como en matchPass), o crear índice por expresión `({col} IS NULL, {col})`. La opción simple: `ORDER BY {sort_col} {order}` tras filtrar NULLs → SQLite usa el índice y evita el temp B-TREE.

#### M6. Watchlist/Compare abren N conexiones SQLite por request y pueden disparar N llamadas en caliente a yfinance
- **Ubicación:** `backend/app/services/company_service.py:38-45` (`get_companies()`) → `26-35` (`get_company()`)
- **Dimensión:** performance-scale
- **Por qué importa:** `get_companies` itera tickers llamando a `get_company`, que hace `connect()/close()` por invocación: para M tickers, M conexiones (apertura de fichero + PRAGMA WAL + synchronous cada una). Si algún ticker no tiene snapshot `ok`, cae a `build_company()` con llamadas de red SÍNCRONAS a yfinance (`get_info` + `get_income_stmt`) y reintentos (`_retry` hasta 3); M tickers no cacheados pueden bloquear el endpoint segundos.
- **Fix:** Query batch (`SELECT data FROM company_snapshot WHERE symbol IN (...) AND status='ok'`) con UNA sola conexión y construir las `Company` desde esos blobs; reservar el fallback live solo para los que falten y preferiblemente no hacerlo síncrono en el request de lista. Reutilizar conexión por request.

#### M7. `add_job` sin `max_instances` ni `misfire_grace_time`: un job más largo que el intervalo se descarta silenciosamente
- **Ubicación:** `backend/app/main.py:48` (`scheduler.add_job(...)`)
- **Dimensión:** performance-scale
- **Por qué importa:** Verificado con APScheduler 3.11.2: `max_instances=1` y `coalesce=True` por defecto. El cron diario (`0 6 * * *`) puede durar horas (14k × 0.7s); si sigue corriendo al próximo disparo, el disparo es MISFIRE y con `misfire_grace_time` por defecto (1s) se descarta → refrescos saltados sin alerta.
- **Fix:** Pasar `misfire_grace_time` amplio (p.ej. 3600) y, si interesa, `coalesce=True`; añadir listener `EVENT_JOB_MISSED`/`EVENT_JOB_ERROR` que registre los misfires. Idealmente mover el job fuera del proceso (ver H2).

#### M8. La caché en disco (diskcache) usa ruta relativa y no está en el volumen
- **Ubicación:** `backend/app/cache/store.py:12` (`_cache = Cache(".cache")`)
- **Dimensión:** deploy-ops
- **Por qué importa:** La caché TTL on-demand (info/precios/financials) vive en `/app/.cache`, capa efímera del contenedor. Cada `docker compose up --build`/recreate la pierde → ráfaga de llamadas a yfinance (rate-limit, latencia, 404 en `/financials` hasta recalentar). Además `/app` es de root y de la capa de imagen: no escribible con usuario no-root sin ajustes.
- **Fix:** Ruta configurable apuntando al volumen persistente, p.ej. `Cache(os.path.join(os.path.dirname(settings.db_path) or '.', 'cache'))` o setting `CACHE_DIR=/data/cache`; crear el dir con permisos del usuario de la app.

#### M9. `proxy_read_timeout` de 60s puede cortar `/financials` (3 llamadas yfinance con reintentos)
- **Ubicación:** `nginx.conf` → `location /api/ { ... proxy_read_timeout 60s; }`
- **Dimensión:** deploy-ops
- **Por qué importa:** Un `/companies/{ticker}/financials` en frío hace 3 fetches a Yahoo, cada uno con hasta 3 intentos y backoff (1s, 2s). Bajo rate-limit/lentitud, el peor caso supera 60s y nginx devuelve 504 aunque el backend siga. Solo se fija `proxy_read_timeout`; no hay `proxy_connect_timeout` ni `proxy_send_timeout`.
- **Fix:** Subir timeouts para esta ruta (`proxy_read_timeout 120s; proxy_send_timeout 120s; proxy_connect_timeout 10s;`), idealmente en un `location` más específico, y/o cargar los 3 estados de forma concurrente en backend.

#### M10. Sin límites de recursos (memoria/CPU) en docker-compose
- **Ubicación:** `docker-compose.yml:9-23` (backend) y `25-34` (frontend): sin `deploy.resources` ni `mem_limit`
- **Dimensión:** deploy-ops
- **Por qué importa:** El job carga DataFrames de pandas/yfinance para ~13.8k tickers y acumula escrituras por lotes; el WAL crece. Sin límites, un pico del scheduler puede agotar la RAM del host (OOM del host, no del contenedor) y degradar el resto. `restart: unless-stopped` reiniciaría en bucle si revienta al arrancar.
- **Fix:** Añadir límites (compose v2): `mem_limit: 1g` y `cpus: "1.0"` al backend (o `deploy.resources.limits`), dimensionados tras medir el job de refresh.

#### M11. `revenue` (financialCurrency) se mezcla con `marketCap`/`price`/`fcfYield` (divisa de cotización) sin etiqueta de divisa — backend
- **Ubicación:** `backend/app/ingest/mappers.py:42-55` (`revenue_and_years`) + `89-122` (`info_to_company`); modelo `backend/app/models/company.py:25-65`
- **Dimensión:** data-correctness
- **Por qué importa:** `Company.revenue` viene del income_stmt en financialCurrency (a menudo USD para empresas UK/CA), mientras `price`/`prevClose`/`marketCap`/`fcfYield` quedan en divisa de cotización (GBP/CAD; UK ya dividido por 100). El modelo `Company` solo guarda `currency` (cotización), no `financialCurrency`, así que el front no puede saber que difieren.
- **Fix:** Añadir `financialCurrency: str | None` al modelo `Company` y rellenarlo desde `info.get('financialCurrency')`. (Habilita la corrección en frontend, M12.)

#### M12. DCF y P/S mezclan `revenue` (financialCurrency) con `marketCap`/`price` (cotización) — frontend
- **Ubicación:** `src/screens/ValuationFinancials.jsx:68-72` (`ValuationBody`) y strip de ratios `389-391`
- **Dimensión:** data-correctness
- **Por qué importa:** `shares = marketCap/price` y `baseFCF = marketCap*fcfYield/100` están en divisa de cotización, pero `lastRev = revenue[last]` en financialCurrency. Para empresas UK/CA que reportan en USD, el DCF y `FCF margin`/`Capex/rev` comparan magnitudes en divisas distintas → cifras erróneas sin aviso. Es la manifestación visible de M11.
- **Fix:** Una vez `Company` exponga `financialCurrency`, detectar el desajuste y (a) convertir con FX o (b) deshabilitar/avisar en el DCF y ocultar ratios cruzados cuando `financialCurrency != currency`.

#### M13. Un pilar puntúa alto con un solo factor presente; el composite renormaliza a peso casi pleno
- **Ubicación:** `backend/app/services/scoring.py:73-79` (`_pillar`) y `82-86` (`_composite`)
- **Dimensión:** data-correctness
- **Por qué importa:** Un pilar es la media de percentiles de los factores DISPONIBLES, sin cobertura mínima. Una empresa con un único factor (p.ej. solo `divYield`) puede dar `value=95`, y si solo tiene ese pilar, `_composite` renormaliza y devuelve `composite≈95`. El caveat está en el docstring pero no mitigado; afecta al ranking del screener y al sort por composite.
- **Fix:** Exigir cobertura mínima: `None` en `_pillar` si `len(vals) < umbral` (p.ej. 2 factores o fracción del pilar); en `_composite` exigir ≥2 pilares no nulos antes de emitir composite; documentar el umbral.

#### M14. Percentiles por mercado con grupos pequeños / factores escasos producen scores ruidosos (UK tras `gbp_only`)
- **Ubicación:** `backend/app/services/scoring.py:92-114` (`compute_scores`) y `63-70` (`_percentile`)
- **Dimensión:** data-correctness
- **Por qué importa:** Los percentiles se calculan por mercado y factor sobre los valores disponibles. Tras `uk_gbp_only` el universo UK es pequeño y factores poco poblados (`epsGrowth`, `peg`, `currentRatio`) pueden tener n muy bajo; con n=1-3 el percentil midrank es casi arbitrario (n=1→50; n=2→25/75) y domina pilares de un solo factor. No hay n mínimo por factor.
- **Fix:** Imponer n mínimo por (mercado, factor) para que el percentil cuente (p.ej. ignorar si n<10) y/o calcular sobre un universo combinado mayor cuando el mercado sea pequeño; documentar el umbral.

#### M15. DCF: la rejilla de sensibilidad puede calcular WACC ≤ crecimiento terminal (r − g ≤ 0) → fair value sin sentido
- **Ubicación:** `src/screens/ValuationFinancials.jsx:95` (`tv = last*(1+g)/(r-g)`), `108-109` (`waccRange`/`termRange`)
- **Dimensión:** frontend-contract
- **Por qué importa:** La fórmula de Gordon no protege contra `r <= g`. La rejilla desplaza WACC −2 y terminal +1: con WACC=5 y terminal=4 (válidos), la celda term=5% / wacc=3% da `(r-g)=-0.02` → terminal value negativo enorme y fair value absurdo, sin aviso. Si `r==g`, división por cero → Infinity/NaN.
- **Fix:** Guardar la perpetuidad: si `(r - g) <= 0.005` devolver `fair = null` y renderizar `—` en esa celda; o clamp del `termRange` para que nunca supere `wacc-spread`.

---

### Low

#### L1. `revenue_and_years` no deduplica por año mientras `build_financials` sí → el sparkline de ingresos puede desalinearse de la pantalla Financials
- **Ubicación:** `backend/app/ingest/mappers.py:42-57` (`revenue_and_years`) vs `142-151` (`_columns_by_year`)
- **Dimensión:** backend-correctness
- **Por qué importa:** `build_financials` colapsa columnas al primer valor por año; `revenue_and_years` no deduplica, así que dos columnas con el mismo `.year` (típico cuando aparece una columna TTM además de la anual) generan DOS entradas para el mismo año en `revenue`/`revenueYears`, mientras Financials muestra una. El sparkline y la tabla dejan de cuadrar.
- **Fix:** Deduplicar por año conservando el más reciente, igual que `_columns_by_year` (dict `{year: value}` antes de invertir), o reutilizar `_columns_by_year(income_df)` + `_sv` para `Total Revenue`.

#### L2. `fcfYield`/`peg`: un valor `0.0` legítimo se convierte en `None` por truthiness en lugar de `is not None`
- **Ubicación:** `backend/app/ingest/mappers.py:109` (`fcfYield`) y `104` (`peg`)
- **Dimensión:** backend-correctness / data-correctness *(fusión: solapa con el hallazgo de `peg or`)*
- **Por qué importa:** `fcfYield=(fcf/mc_abs*100) if (fcf and mc_abs) else None`: con `fcf == 0.0` (dato válido) la guarda es falsa y se pierde el 0.0 (`—` en UI). Mismo patrón en `peg=_num(trailingPegRatio) or _num(pegRatio)`: un `trailingPegRatio == 0.0` o negativo se descarta por el `or` y cae a `pegRatio`, mezclando métricas.
- **Fix:** Comprobaciones explícitas: `fcfYield = (fcf/mc_abs*100) if (fcf is not None and mc_abs) else None` (`mc_abs` sí debe excluir 0 para no dividir por cero). Para peg, elegir por presencia: `t=_num(info.get('trailingPegRatio')); peg = t if t is not None else _num(info.get('pegRatio'))`.

#### L3. `search_universe` usa `LIKE` con `q` sin escapar `%`/`_` → comodines del usuario alteran la búsqueda
- **Ubicación:** `backend/app/db/queries.py:128-138` (`search_universe`)
- **Dimensión:** backend-correctness
- **Por qué importa:** `like = f"%{q}%"` interpreta `%` y `_` del input como comodines (no hay inyección, los params están bindeados): buscar `A_B` o `100%` devuelve coincidencias inesperadas. Confuso en la barra global (⌘K).
- **Fix:** Escapar antes de envolver (`q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')`) y añadir `ESCAPE '\\'` a las cláusulas LIKE.

#### L4. CORS con `allow_methods` y `allow_headers` comodín; configuración por defecto solo apta para desarrollo
- **Ubicación:** `backend/app/main.py:61-66` (`CORSMiddleware`)
- **Dimensión:** security
- **Por qué importa:** `allow_methods=["*"]` y `allow_headers=["*"]`; `allow_origins` por defecto `http://localhost:5173` (config.py:15). Sin separación dev/prod ni validación de un origen real en producción. (`allow_credentials=False` mitiga el peor caso.)
- **Fix:** Restringir a métodos usados (`["GET"]`) y cabeceras necesarias; forzar `CORS_ORIGINS` con el dominio de producción y fallar el arranque si queda el default en prod.

#### L5. Dependencias declaradas con floors abiertos en pyproject (mitigado por `uv.lock` + `--frozen`)
- **Ubicación:** `backend/pyproject.toml:6-16` (`[project] dependencies`)
- **Dimensión:** security
- **Por qué importa:** Todas las deps con cota inferior abierta sin techo (`fastapi>=0.115`, `yfinance>=0.2.50`). Mitigado por `uv.lock` commiteado y `uv sync --frozen --no-dev`, pero cualquier `uv sync` sin `--frozen` traería versiones nuevas sin revisión; sin escaneo de vulnerabilidades en CI.
- **Fix:** Mantener `--frozen` en todos los entornos, añadir `pip-audit` en CI y fijar techos para dependencias sensibles como yfinance.

#### L6. Sort y filtros del screener sobre columnas sin índice (`peg`, `pb`, `div_yield`, `roe`, `rev_growth`, `price`, scores)
- **Ubicación:** `backend/app/db/schema.py:60-63` (índices) vs `_SORT_COLS`/`_SCREEN_FILTERS` en `queries.py:142-160`
- **Dimensión:** performance-scale
- **Por qué importa:** El esquema solo indexa `market`, `score_composite`, `pe`, `market_cap`. El screener ordena/filtra por muchas columnas no indexadas; aun corrigiendo M5, esos ordenamientos seguirían provocando full scan + temp B-TREE. Asumible con ~13k filas pero crece con el universo y la concurrencia.
- **Fix:** Añadir índices para las columnas usadas como sort/filtro frecuente (`idx_snap_peg`, `idx_snap_div_yield`, `idx_snap_roe`, `idx_snap_rev_growth`, scores, y price si se ordena). Considerar índices compuestos con `status` como primera columna (todas las queries filtran `status='ok'`).

#### L7. `search_universe` usa `LIKE` con comodín inicial `%q%` → full scan del universo (~13.8k) + temp B-TREE por pulsación
- **Ubicación:** `backend/app/db/queries.py:128-138` (`search_universe`)
- **Dimensión:** performance-scale
- **Por qué importa:** El comodín inicial impide usar `idx_universe_name`. `EXPLAIN` confirma `SCAN u` + `USE TEMP B-TREE`. Como search se dispara por teclado, cada keystroke recorre ~13.8k filas, hace LEFT JOIN y ordena en memoria; con varias sesiones puede saturar.
- **Fix:** Para prefijo de ticker usar `symbol LIKE q||%` (usa índice por PK). Para nombre, sustituir por FTS5 (tabla virtual de symbol+name) o al menos prefijo `name LIKE q||%`. Con FTS la búsqueda es O(log n).

#### L8. Conexión SQLite por request con PRAGMA WAL/synchronous re-aplicados en cada apertura
- **Ubicación:** `backend/app/db/schema.py:67-77` (`connect()`); usada por todos los services
- **Dimensión:** performance-scale
- **Por qué importa:** Cada service hace `connect()/close()` por request, y `connect()` ejecuta `os.makedirs` + PRAGMA WAL + synchronous en CADA apertura. Bajo concurrencia añade syscalls innecesarios (creación de dir, pragmas ya persistidos) y descarta el page cache por conexión. Coste evitable en el camino caliente.
- **Fix:** `journal_mode=WAL` es persistente: setearlo una vez al init. Mantener conexión por hilo (thread-local) o pool ligero; mover `os.makedirs` al arranque. `synchronous=NORMAL` (por-conexión) fijarlo en una factoría reutilizada.

#### L9. Paginación por OFFSET y respuesta con blob JSON por fila: `COUNT(*)` full scan + materialización de blobs grandes
- **Ubicación:** `backend/app/db/queries.py:176-178` (COUNT) y `183-187` (blobs); `list_company_data:118-125`
- **Dimensión:** performance-scale
- **Por qué importa:** `screen()` ejecuta un `COUNT(*)` sobre el WHERE (segundo scan) por request, y ambos endpoints devuelven la columna `data` (JSON completo del Company) re-parseado con `model_validate_json` (hasta 200 blobs por request). Con OFFSET alto, SQLite recorre y descarta las filas saltadas. Dos scans + deserialización masiva por página.
- **Fix:** Tras corregir M5, para paginación profunda usar keyset (`WHERE sort_col < :last`). Cachear el COUNT por combinación de filtros o devolverlo solo en la primera página. Si la UI no necesita todos los campos en el listado, devolver columnas concretas en vez del blob.

#### L10. Múltiples workers de uvicorn duplicarían los jobs del scheduler
- **Ubicación:** `backend/app/main.py:32-49` (`lifespan()`, `BackgroundScheduler` dentro del proceso web)
- **Dimensión:** deploy-ops
- **Por qué importa:** Hoy funciona con un único worker, pero `--workers N` (o gunicorn) haría que cada worker arranque su propio scheduler y el cron diario se ejecute N veces simultáneamente (martilleo a Yahoo, escrituras concurrentes, posibles bloqueos pese a WAL). Relacionado con H2.
- **Fix:** Aislar el scheduler: documentar/forzar single-worker (`--workers 1`) o ejecutarlo como servicio/proceso separado con `ENABLE_SCHEDULER=false` en el web. Para multi-worker, jobstore con lock o elección de líder.

#### L11. `frontend` depende de `backend` sin esperar a que esté healthy
- **Ubicación:** `docker-compose.yml:32-33` (`depends_on: - backend`)
- **Dimensión:** deploy-ops
- **Por qué importa:** El backend tiene healthcheck completo, pero el frontend solo espera a que el contenedor esté creado/iniciado, no a que `/health` responda. En el primer arranque, nginx puede recibir `/api` antes de que el backend acepte conexiones → 502 momentáneos (nginx reintenta después, de ahí severidad baja).
- **Fix:** Forma larga: `depends_on:\n  backend:\n    condition: service_healthy` (compose v2.x), aprovechando el healthcheck ya definido.

#### L12. Defaults de CORS y scheduler heredados del `.env` podrían filtrarse a producción
- **Ubicación:** `backend/app/config.py:15` (`cors_origins='http://localhost:5173'`); `12` (`env_file='.env'`)
- **Dimensión:** deploy-ops
- **Por qué importa:** En compose el frontend va por mismo origen vía nginx (`/api`), así que CORS no se usa y el default es inocuo ahí; pero si se expone el backend directamente, el único origen permitido sería `localhost:5173` (dev). Además se lee `.env` si existe en `/app`, acoplando el comportamiento a la presencia de un fichero. No es bug activo en el stack actual.
- **Fix:** Definir `CORS_ORIGINS` explícito por entorno en `docker-compose.yml` (o documentar que en prod va por proxy) y considerar deshabilitar la lectura de `.env` en imagen (configuración solo por variables de entorno).

#### L13. `useAsync` borra `data` en cada refetch → parpadeo y pérdida de la lista previa
- **Ubicación:** `src/api.js:39-49` (`setState({ loading: true, error: null, data: null })`)
- **Dimensión:** frontend-contract
- **Por qué importa:** En cada cambio de deps se descarta `data` y se muestra `<Loading/>` a pantalla completa. En Screener cada movimiento de slider o cambio de orden vacía la tabla; igual en Watchlist/Compare al añadir/quitar un ticker. Parpadeo notorio.
- **Fix:** No resetear `data` a null: `setState((s) => ({ ...s, loading: true, error: null }))`; que las pantallas distingan "loading inicial" (`data == null`) de "refetch" (`data != null`) para no desmontar la tabla.

#### L14. `useAsync` re-ejecuta `fn` al cambiar su identidad aun con deps estables (cierres en arrow inline)
- **Ubicación:** `src/api.js:49` (`// eslint-disable-line react-hooks/exhaustive-deps`) y callsites en App.jsx/screens
- **Dimensión:** frontend-contract
- **Por qué importa:** `useAsync` recibe una arrow nueva por render pero solo re-ejecuta con las deps explícitas y exhaustive-deps deshabilitado. Intencional, pero frágil: si alguien añade en `fn` una variable que no está en deps, servirá datos stale en silencio. Trampa de mantenimiento, no bug actual.
- **Fix:** Convención: pasar como deps TODO lo que `fn` lee (ya se hace hoy), o refactor a `useCallback(fn, deps)` y depender de `[fn]` para que el linter valide. Mantener invariante en revisión de PRs.

#### L15. DCF: `FcfBars` produce NaN (0/0) cuando el FCF inicial es 0
- **Ubicación:** `src/screens/ValuationFinancials.jsx:231` (`max = Math.max(...flows.map(f=>f.fcf))`), `238` (`height: (f.fcf/max)*80`), `71` (`baseFCF`)
- **Dimensión:** frontend-contract
- **Por qué importa:** Si no hay revenue (`lastRev=0`) y `fcfYield` es null, `baseFCF=0` y el estado inicial `inp.fcf=0` (el clamp `min=1` solo aplica al editar). Con `inp.fcf=0`, todos los `flows.fcf=0`, `max=0` y `f.fcf/max = 0/0 = NaN`; las barras reciben `height` NaN. El guard `if (!mc || !c.price)` no cubre `fcf=0`.
- **Fix:** Forzar FCF base positivo: `fcf: +Math.max(0.1, baseFCF).toFixed(1)` en el estado inicial; en `FcfBars` usar `const max = Math.max(1e-9, ...flows.map(f=>f.fcf))` y proteger `f.pv/f.fcf` contra `fcf=0`.

#### L16. Watchlist: `gainers` cuenta mal con `change` null
- **Ubicación:** `src/screens/WatchlistOverview.jsx:34` (`gainers = rows.filter(c=>c.change>0).length`), `47` (`${rows.length-gainers} declining`)
- **Dimensión:** frontend-contract
- **Por qué importa:** `change` es float obligatorio, pero si viniera null/NaN, `c.change > 0` es false y cae en "declining" aunque no esté bajando; `X declining = total - gainers` mezcla "sin dato" con "a la baja". Caso límite.
- **Fix:** Contar explícitamente: `adv = filter(change>0)`, `dec = filter(change<0)`; mostrar `${dec} declining` (opcional `flat = total-adv-dec`).

#### L17. Reflexión de la entrada del usuario en el `detail` de HTTPException
- **Ubicación:** `backend/app/routers/companies.py:34` (también `prices.py:20`, `financials.py:20`)
- **Dimensión:** security
- **Por qué importa:** `detail=f"Sin datos para {ticker}"` refleja el valor crudo del cliente. Combinado con la falta de validación (M1), permite eco de payloads arbitrarios en la respuesta JSON. Riesgo XSS bajo (respuesta JSON), pero la reflexión sin sanear facilita el sondeo.
- **Fix:** Validar/normalizar el ticker antes (M1) y/o mensaje fijo sin reflejar la entrada: `detail="Sin datos para el ticker solicitado"`.

#### L18. `dividendYield` se asume en puntos % (yfinance 1.4.1) pero pyproject permite `>=0.2.50` (fracción)
- **Ubicación:** `backend/app/ingest/mappers.py:108` (`divYield`) y comentario de cabecera `:8`
- **Dimensión:** data-correctness
- **Por qué importa:** `divYield=_num(info.get('dividendYield'))` no multiplica por 100, apoyándose en que 1.4.1 entrega puntos %. Pero pyproject declara `yfinance>=0.2.50`; en 0.2.x viene como FRACCIÓN (0.0035), con lo que el yield quedaría 100× menor, contaminando el factor `divYield` y la columna `div_yield`. La verificación está atada a una versión que el rango no garantiza.
- **Fix:** Fijar el rango a la familia verificada (`yfinance>=1.4,<2`) o normalizar defensivamente (si `dividendYield < 1`, heurística de fracción, ×100), para no depender de la versión instalada.

#### L19. Compare: añadir un 6º ticker cuando ya hay 5 descarta silenciosamente el recién añadido
- **Ubicación:** `src/screens/ScreenerCompare.jsx:209` (`setSet((s)=>(s.includes(t)?s:[...s,t]).slice(0,5))`)
- **Dimensión:** frontend-contract
- **Por qué importa:** `[...s, t].slice(0, 5)` conserva los 5 primeros y descarta `t`. El botón Add se oculta con `cos.length>=5` (datos cargados, no `set`): si una compañía falla al cargar, Add reaparece y el usuario añade un ticker que se pierde sin feedback.
- **Fix:** Recortar por el principio para respetar el último añadido: `setSet((s)=> s.includes(t) ? s : [...s, t].slice(-5))`; mismo criterio en `App.jsx go()` (ver L20).

#### L20. `App.jsx go('compare')` usa `slice(0,5)` → inconsistente con `slice(-5)` y con el default de 4
- **Ubicación:** `src/App.jsx:113` (`setCompareSet((s) => s.includes(ticker) ? s : [...s, ticker].slice(0, 5))`)
- **Dimensión:** frontend-contract
- **Por qué importa:** Desde una ficha, si `compareSet` ya tiene 5, el ticker en el que el usuario hizo clic para comparar se descarta y la navegación a Compare no lo muestra. Misma clase de bug que L19; convive con `AddSearch` (slice(0,5)) y default inicial 4.
- **Fix:** Usar `slice(-5)` para que el ticker recién solicitado siempre entre: `setCompareSet((s)=> s.includes(ticker) ? s : [...s, ticker].slice(-5))`.

#### L21. `api.js` no normaliza barras al combinar BASE + path
- **Ubicación:** `src/api.js:12` (`new URL(BASE + path, window.location.origin)`)
- **Dimensión:** frontend-contract
- **Por qué importa:** Con `BASE` absoluto o relativo funciona, pero `VITE_API_URL` con barra final + path sin/ con barra inicial produce `//companies` (doble barra) que algunos proxies normalizan mal. No hay normalización.
- **Fix:** Normalizar: `const base = BASE.replace(/\/$/, ''); const url = new URL(base + path, window.location.origin);` y documentar que `VITE_API_URL` no debe llevar barra final.

#### L22. `ScoreRing`/`ScoreBar`/`CompositeMini` asumen score 0–100; fuera de rango desborda el anillo/barra sin clamp
- **Ubicación:** `src/components/ui.jsx:211` (`strokeDashoffset = circ*(1 - score/100)`), `237` (`width: (score??0)+'%'`); `shared.jsx:51` (`width: score+'%'`)
- **Dimensión:** frontend-contract
- **Por qué importa:** `scoreColor` ya clampea, pero `ScoreRing`/`ScoreBar`/`CompositeMini` no: `score>100` desborda el arco/contenedor, `score<0` invierte. Un bug de scoring aguas arriba rompería la UI en vez de degradar limpio.
- **Fix:** Clampear en los tres sitios: `const s = Math.max(0, Math.min(100, score));` usar `s` para dashoffset/width.

#### L23. `CompanyOverview` ignora el rango seleccionado y siempre pide `'1Y'`
- **Ubicación:** `src/screens/WatchlistOverview.jsx:141` (`api.prices(ticker,'1Y')`), `147-150` (closes/lo/hi), `148` (slice por `RANGE_DAYS`)
- **Dimensión:** frontend-contract
- **Por qué importa:** Siempre pide 1Y y recorta en cliente con `slice(-RANGE_DAYS[range])`; `lo`/`hi` (52-wk) se calculan sobre toda la serie 1Y (correcto), pero se desaprovecha el parámetro `range` del contrato (transferencia innecesaria). `RANGE_DAYS` usa días de trading aproximados (22/63/126/252) que pueden no coincidir con los puntos reales (festivos).
- **Fix:** Mantener 1Y para el 52-wk (documentarlo) o, si se usa el contrato, pedir `api.prices(ticker, range)` con deps `[ticker, range]` y calcular 52-wk de una serie 1Y separada. Como mínimo, recortar por fecha real en vez de por nº fijo de puntos.

#### L24. Financials: `FCF margin` / `Capex/rev` mezclan magnitudes si revenue y fcf/capex no comparten año
- **Ubicación:** `src/screens/ValuationFinancials.jsx:389-391` (`lastVal('fcf')/lastVal('revenue')`, `lastVal('capex')/lastVal('revenue')`)
- **Dimensión:** frontend-contract
- **Por qué importa:** `lastVal(k)` toma `data[data.length-1][k]` (último año). Si el último año tiene fcf/capex pero revenue null (o viceversa, p.ej. cashflow más reciente que income), el ratio muestra `—` aunque haya datos en el penúltimo. No garantiza que ambos vengan del último año con AMBOS valores.
- **Fix:** Calcular sobre el último año donde ambas claves no sean null: `const lastBoth=(a,b)=>{ for(let i=data.length-1;i>=0;i--){ if(data[i][a]!=null && data[i][b]) return [data[i][a],data[i][b]]; } return null; };` y usarlo para FCF margin y Capex/rev.

#### L25. Símbolos Aquis (`.AQ` con infijo `-GB`) pasan sin validación; `to_yahoo` no los normaliza
- **Ubicación:** `backend/app/universe/normalize.py:32-37` (`to_yahoo`, solo transforma US) + `providers.fetch_universe:75`
- **Dimensión:** data-correctness
- **Por qué importa:** AQS (Aquis) aporta ~274 acciones GBP que pasan `is_kept`, con símbolos como `AAAP-GB.AQ`/`ADB.AQ`. `to_yahoo` deja los no-US tal cual; `.AQ`/`-GB` no es el formato Yahoo habitual de LSE (`.L`), así que muchos podrían no resolver en yfinance → filas `status='error'` silenciosas para todo un sub-mercado UK.
- **Fix:** Validar el formato Aquis contra yfinance en una pasada de muestreo; si `.AQ`/`-GB` no resuelve, añadir el mapeo correcto en `to_yahoo` (o excluir AQS hasta confirmar) para no contaminar el universo UK.

---

## Notas y límites

### Alcance de la auditoría
- Cubre seis dimensiones: **backend-correctness, security, performance-scale, frontend-contract, data-correctness y deploy-ops**.
- Componentes revisados: backend FastAPI (routers, services, ingest/mappers, scoring, db/queries+schema, jobs/scheduler, cache, universe), frontend React/Vite (api.js, App.jsx, screens, componentes ui/shared) e infraestructura (Dockerfile, docker-compose.yml, nginx.conf, pyproject/uv.lock).
- Los hallazgos de rendimiento se verificaron con `EXPLAIN QUERY PLAN` sobre el esquema real; el comportamiento del scheduler con APScheduler 3.11.2 instalado; y las rutas de yfinance contra el código de la dependencia (`scrapers/quote.py`, `scrapers/history.py`).

### Deduplicación aplicada (solapamientos fusionados)
La lista original tenía 42 entradas; se fusionaron 6 pares/duplicados en un único hallazgo cada uno (42 − 6 = 36):
1. **Contenedor backend como root** — reportado en `security` y en `deploy-ops` → **M3**.
2. **nginx sin cabeceras de seguridad / sin gzip / sin límite de tamaño** — `security` (cabeceras + límite) y `deploy-ops` (gzip + cabeceras + cache) → **M4**.
3. **`peg` con truthiness/`or`** — entrada de `backend-correctness` (fcfYield/peg) y de `data-correctness` (peg con `or`) → **L2**.

> Cada fusión conserva la severidad más alta de las entradas combinadas y consolida sus fixes.

### Falsos positivos / no-bugs descartados (6)
Estos puntos se incluyeron en la lista verificada pero son **no-bugs actuales o riesgos solo latentes**, conservados como deuda/convención, no como defectos activos:
1. **L5** Floors abiertos en pyproject — mitigado por `uv.lock` + `--frozen`; no es bug activo, es endurecimiento de CI.
2. **L12** Defaults de CORS/scheduler vía `.env` — inocuo en el stack actual (mismo origen vía nginx); riesgo solo si se expone el backend directamente.
3. **L14** `useAsync` re-ejecución por identidad de `fn` — comportamiento intencional; trampa de mantenimiento, no bug actual.
4. **L20**/**L19** límite de 5 en Compare — el caso solo se alcanza si una compañía falla al cargar y reaparece el botón Add; degradación de UX, no corrupción de datos.
5. **L23** `CompanyOverview` pide siempre 1Y — el cálculo de 52-wk es correcto; es desaprovechamiento del contrato y transferencia extra, no dato erróneo.
6. **L4** CORS comodín en métodos/headers — `allow_credentials=False` mitiga el peor caso; relevante solo en despliegue laxo, no explotable en la configuración por defecto.

### Recomendación de priorización
1. **Inmediato (High):** corregir el filtro `status='ok'` del backfill (H1, una línea) y planificar la salida del job del proceso web (H2).
2. **Antes de exponer públicamente (Medium de seguridad):** validación del ticker (M1), rate limiting (M2), usuario no-root (M3), endurecer nginx (M4).
3. **Rendimiento (Medium/Low):** eliminar `IS NULL` del ORDER BY (M5) y batch en watchlist/compare (M6); luego índices y FTS5 (L6, L7).
4. **Datos:** exponer `financialCurrency` (M11/M12) y reforzar el scoring (M13/M14); fijar la versión de yfinance (L18).
