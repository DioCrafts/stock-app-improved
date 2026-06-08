# Informe de discrepancias de UI — correcciones concretas

**Fecha:** 2026-06-08
**Rama:** `claude/clever-gates-qn2YY`
**Alcance:** comparación de la implementación del repo contra los 5 ficheros de referencia facilitados (`ui.jsx`, `app.jsx`, `screens-watchlist-overview.jsx`, `screens-screener-compare.jsx`, `Terminal_1.html`).

> **Pendiente:** falta el `screens-val-fin.jsx` y el `data.js` de referencia. No se incluyen correcciones para la pantalla **Valuation / Financials** ni para datos semilla (watchlist por defecto, valores de índices) hasta disponer de ellos.

---

## Resumen ejecutivo

- **Estilo visual: sin discrepancias.** `src/index.css` ≡ `<style>` de `Terminal_1.html` (tokens, sombras, radios, tipografías). Todos los componentes conservan tamaños, paddings, colores y estructura del prototipo.
- Las diferencias reales son: **5 de texto** (`en.json`), **1 de layout** (pie del sidebar) y **varias de comportamiento** que en realidad son **mejoras** (no conviene revertirlas).
- Clasificación:
  - **Correcciones seguras** (alinear con el prototipo, sin ambigüedad): **C4**.
  - **Decisiones de producto** (prototipo vs. versión actual; tu elección): **C1, C2, C3, C5, C6**.
  - **Divergencias intencionales — NO revertir**: **D1–D5**.

---

## Tabla de priorización

| ID | Tipo | Fichero | Severidad | Acción recomendada |
|----|------|---------|-----------|--------------------|
| C4 | Texto | `src/i18n/en.json:123` | Baja (omisión clara) | **Aplicar** (alinear) |
| C1 | Texto | `src/i18n/en.json:85` | Baja | Decidir |
| C2 | Texto | `src/i18n/en.json:92` | Baja | Decidir |
| C3 | Texto | `src/i18n/en.json:114` | Baja | Decidir (mejor: dinámico) |
| C5 | Texto/estructura | `src/i18n/en.json:137-138` | Media | Decidir |
| C6 | Layout | `src/App.jsx:193-201` | Media | Mantener (recomendado) |
| D1–D5 | Comportamiento | varios | — | No revertir |

> Nota: las cadenas equivalentes en `src/i18n/es.json` deben actualizarse en paralelo a cualquier cambio de `en.json`.

---

## Correcciones de TEXTO (`en.json`)

### C4 — Sub-score "Value": falta «, DCF» *(corrección segura)*

El prototipo etiqueta el sub-score Value como `ratios, DCF`; el repo perdió «, DCF».

- **Prototipo** (`screens-watchlist-overview.jsx:286`): `<ScoreBar label="Value" sub="ratios, DCF" … />`
- **Actual** (`en.json:123`):
  ```json
  "value": "ratios",
  ```
- **Propuesto:**
  ```json
  "value": "ratios, DCF",
  ```
- **es.json:** `"value": "ratios, DCF"` (o equivalente ya traducido).

---

### C1 — Subtítulo Watchlist: bolsas adicionales *(decisión)*

- **Prototipo** (`screens-watchlist-overview.jsx:62`): `… companies tracked · NYSE / NASDAQ`
- **Actual** (`en.json:85`):
  ```json
  "subtitle": "{{count}} companies tracked · NYSE / NASDAQ / TSX / LSE",
  ```
- **Si quieres fidelidad al prototipo:**
  ```json
  "subtitle": "{{count}} companies tracked · NYSE / NASDAQ",
  ```
- **Criterio:** mantener `TSX / LSE` **solo si** el universo del backend realmente incluye cotizadas de esas bolsas. Si es así, el texto actual es más correcto que el prototipo → **no cambiar**.

---

### C2 — Footer Watchlist: redacción de los scores *(decisión)*

- **Prototipo** (`screens-watchlist-overview.jsx:130`):
  `Click any row to open the company. Scores are illustrative composites — Value 35% · Growth 30% · Health 20% · Momentum 15%.`
- **Actual** (`en.json:92`):
  ```json
  "footer": "Click any row to open the company. Scores: Value 35% · Growth 30% · Health 20% · Momentum 15% (percentiles by market)."
  ```
- **Si quieres fidelidad al prototipo:**
  ```json
  "footer": "Click any row to open the company. Scores are illustrative composites — Value 35% · Growth 30% · Health 20% · Momentum 15%."
  ```
- **Criterio:** «illustrative composites» encaja con datos mock; «percentiles by market» encaja con datos reales del backend. Elige según la naturaleza real de los scores que sirve la API.

---

### C3 — Título card Revenue: se perdió «— 6Y» *(decisión; mejor: dinámico)*

- **Prototipo** (`screens-watchlist-overview.jsx:293`): `Revenue — 6Y ($B)`
- **Actual** (`en.json:114`):
  ```json
  "revenue": "Revenue ($B)",
  ```
- **Causa:** en el prototipo el «6Y» estaba hardcodeado (siempre 6 años); en el repo `RevenueBars` recibe `c.revenue` de **longitud variable** desde el backend, por eso se quitó el número fijo.
- **Opción A — fidelidad al prototipo** (solo si el backend siempre da 6 años):
  ```json
  "revenue": "Revenue — 6Y ($B)",
  ```
- **Opción B — recomendado: dinámico.** Interpolar el nº de años:
  ```json
  "revenue": "Revenue — {{count}}Y ($B)",
  ```
  y en `src/screens/WatchlistOverview.jsx:270` pasar el conteo:
  ```jsx
  <Card title={t("company.card.revenue", { count: c.revenue?.length ?? 0 })} pad={16}>
  ```

---

### C5 — Subtítulo Screener: «X of Y companies match» → «N matches» *(decisión)*

- **Prototipo** (`screens-screener-compare.jsx:87`):
  `{results.length} of {DATA.companies.length} companies match` + ` · N active filters` / ` · no filters`
- **Actual** (`en.json:137-138`): `"{{count}} matches"` + ` · showing first {{count}}` + filtros.
- **Causa:** el backend devuelve `total` (coincidencias) y `results` (limitado a 100, ver `ScreenerCompare.jsx:59`). El «of Y» del prototipo (tamaño del universo) **no llega** en esa respuesta.
- **Alineación máxima sin tocar backend** — acercar la redacción:
  ```json
  "matches": "{{count}} companies match",
  ```
  Resultado: `247 companies match · showing first 100 · 2 active filters`.
- **Fidelidad total** («X of Y companies match») requeriría que la API exponga el tamaño del universo total; es cambio de backend, fuera del alcance de este informe.

---

## Corrección de LAYOUT

### C6 — Pie del sidebar reorganizado por el botón de idioma *(mantener, recomendado)*

- **Prototipo** (`app.jsx:165`): una fila → `ThemeToggle` (izq.) + «Market open» (der.).
- **Actual** (`src/App.jsx:193-201`): columna en dos filas → fila 1 `ThemeToggle` + **`LangToggle`** (nuevo); fila 2 estado de mercado.
- **Causa:** el `LangToggle` (feature i18n, no existía en el prototipo) no cabe en la fila original (sidebar de 212 px).
- **Opción A — recomendado:** mantener tal cual. El cambio está justificado por el selector de idioma.
- **Opción B — volver a una fila como el prototipo** (mover el idioma a la cabecera):
  - En `src/App.jsx:193-201`, restaurar el pie a una sola fila:
    ```jsx
    <div style={{ marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px" }}>
      <ThemeToggle theme={theme} setTheme={setTheme} />
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-3)" }}>
        <span className="live-dot"></span> {marketStatus?.open ? t("shell.marketOpen") : t("shell.marketClosed")}
      </div>
    </div>
    ```
  - Y montar `<LangToggle />` en el `<header>` (`src/App.jsx:206-216`), junto a los `IndexChip`.

---

## Divergencias intencionales — recomiendo NO revertir

| ID | Dónde | Prototipo | Repo | Por qué dejarlo |
|----|-------|-----------|------|-----------------|
| D1 | `WatchlistOverview.jsx:146` | `{1M:22, 3M:60, 6M:60, 1Y:60}` (3M/6M/1Y idénticos) | `{1M:22, 3M:63, 6M:126, 1Y:252}` | Corrige un bug del prototipo: ahora cada rango del gráfico cambia de verdad. |
| D2 | `App.jsx:119`, `ScreenerCompare.jsx:221` | `.slice(0,5)` (al añadir un 6º, lo descarta) | `.slice(-5)` (expulsa al más antiguo) | Mejor UX en Compare. |
| D3 | `ScreenerCompare.jsx:318` (`AddSearch`) | Desplegable con todo el universo | Input de búsqueda con autofocus + debounce | Escala con un universo grande de empresas. |
| D4 | `WatchlistOverview.jsx:38` | `decliners = total − gainers` (0% cuenta como «declining») | `change < 0` estricto | Semánticamente más correcto (0% no es ni sube ni baja). |
| D5 | Global | `DATA` en memoria, sin i18n | API asíncrona (`api.js`) + i18n EN/ES + estados Loading/Error/Empty | Arquitectura de la versión «improved». |

---

## Plan de aplicación sugerido

1. **Aplicar C4** (segura) en `en.json` + `es.json`.
2. **Decidir C1, C2, C3, C5** (texto) — por defecto recomiendo: C1 mantener si hay TSX/LSE reales; C2 según naturaleza de los scores; **C3 → dinámico (Opción B)**; C5 → `"{{count}} companies match"`.
3. **C6** — mantener (Opción A) salvo que prefieras la cabecera (Opción B).
4. **No tocar** D1–D5.
5. Revisar **Valuation / Financials** y **datos semilla** cuando llegue el `screens-val-fin.jsx` y el `data.js` de referencia.
