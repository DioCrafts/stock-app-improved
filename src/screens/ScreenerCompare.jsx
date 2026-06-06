/* ============================================================
   screens-screener-compare.jsx — Screener + Comparator
   ============================================================ */
import { useState, useEffect } from "react";
import { api, useAsync } from "../api.js";
import { fmt, Icon, Mono, Delta, Pill, Card, ScoreRing } from "../components/ui.jsx";
import { Th, Td, ScorePip, PageHead, CompositeMini, Loading, ErrorBox, Empty } from "../components/shared.jsx";

/* =================== SCREENER =================== */
const SCREEN_PRESETS = {
  "All stocks":      {},
  "Deep value":      { peMax: 20, pbMax: 5, valueMin: 60 },
  "GARP":            { pegMax: 1.5, growthMin: 60, valueMin: 40 },
  "Quality growth":  { growthMin: 70, healthMin: 80, roeMin: 20 },
  "Dividend":        { divMin: 2, healthMin: 65 },
  "High momentum":   { momentumMin: 70, growthMin: 55 },
};

// Catálogo de filtros (claves = parámetros del endpoint /screener)
const FILTER_DEFS = [
  { key: "capMin", label: "Market cap ≥", min: 0, max: 3500, step: 50, unit: "$B", cmp: "gte" },
  { key: "peMax", label: "P/E ≤", min: 5, max: 120, step: 1, unit: "×", cmp: "lte" },
  { key: "pegMax", label: "PEG ≤", min: 0.5, max: 5, step: 0.1, unit: "×", cmp: "lte" },
  { key: "pbMax", label: "P/B ≤", min: 1, max: 50, step: 1, unit: "×", cmp: "lte" },
  { key: "divMin", label: "Div yield ≥", min: 0, max: 5, step: 0.1, unit: "%", cmp: "gte" },
  { key: "roeMin", label: "ROE ≥", min: 0, max: 100, step: 5, unit: "%", cmp: "gte" },
  { key: "growthRevMin", label: "Rev growth ≥", min: -10, max: 100, step: 5, unit: "%", cmp: "gte" },
  { key: "valueMin", label: "Value score ≥", min: 0, max: 100, step: 5, unit: "", cmp: "gte" },
  { key: "growthMin", label: "Growth score ≥", min: 0, max: 100, step: 5, unit: "", cmp: "gte" },
  { key: "healthMin", label: "Health score ≥", min: 0, max: 100, step: 5, unit: "", cmp: "gte" },
  { key: "momentumMin", label: "Momentum ≥", min: 0, max: 100, step: 5, unit: "", cmp: "gte" },
];

function Screener({ go, watch, toggleWatch }) {
  const [preset, setPreset] = useState("All stocks");
  const [filters, setFilters] = useState({});
  const [sort, setSort] = useState({ k: "composite", dir: "desc" });

  const applyPreset = (name) => {
    setPreset(name);
    const p = SCREEN_PRESETS[name];
    const f = {};
    FILTER_DEFS.forEach((d) => { if (p[d.key] != null) f[d.key] = p[d.key]; });
    setFilters(f);
  };
  const setFilter = (key, val) => { setFilters((f) => ({ ...f, [key]: val })); setPreset("Custom"); };
  const clearFilter = (key) => { setFilters((f) => { const n = { ...f }; delete n[key]; return n; }); setPreset("Custom"); };

  const { loading, error, data } = useAsync(
    () => api.screen({ ...filters, sort: sort.k, order: sort.dir, limit: 100 }),
    [JSON.stringify(filters), sort.k, sort.dir]);
  const results = data?.results || [];
  const total = data?.total ?? 0;
  const activeFilters = FILTER_DEFS.filter((d) => filters[d.key] != null);

  return (
    <div className="fade-up" style={{ display: "flex", height: "100%", minHeight: 0 }}>
      {/* filter rail */}
      <div style={{ width: 280, flex: "none", borderRight: "1px solid var(--border)", overflowY: "auto", padding: 20, background: "var(--bg-2)" }}>
        <h2 style={{ fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-2)", marginBottom: 12 }}>Factor presets</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 22 }}>
          {Object.keys(SCREEN_PRESETS).map((p) => (
            <Pill key={p} active={preset === p} onClick={() => applyPreset(p)}>{p}</Pill>
          ))}
        </div>
        <h2 style={{ fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-2)", marginBottom: 14 }}>Filters</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {FILTER_DEFS.map((d) => (
            <FilterSlider key={d.key} def={d} value={filters[d.key]}
              onChange={(v) => setFilter(d.key, v)} onClear={() => clearFilter(d.key)} />
          ))}
        </div>
      </div>

      {/* results */}
      <div style={{ flex: 1, minWidth: 0, overflowY: "auto", padding: 24 }}>
        <PageHead title="Screener"
          sub={<span>{total} matches{results.length < total ? ` · showing first ${results.length}` : ""}{activeFilters.length ? ` · ${activeFilters.length} active filter${activeFilters.length > 1 ? "s" : ""}` : " · no filters"}</span>}
          right={activeFilters.length > 0 && <button onClick={() => { setFilters({}); setPreset("All stocks"); }}
            style={{ fontSize: 12, color: "var(--accent)", fontWeight: 600 }}>Reset all</button>} />

        {activeFilters.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
            {activeFilters.map((d) => (
              <Pill key={d.key} tone="accent" onClick={() => clearFilter(d.key)}>
                {d.label} {filters[d.key]}{d.unit} <Icon name="x" size={11} />
              </Pill>
            ))}
          </div>
        )}

        {loading ? <Loading /> : error ? <ErrorBox error={error} /> : (
          <Card pad={0}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <Th k="ticker" sort={sort} setSort={setSort} align="left">Company</Th>
                    <Th k="price" sort={sort} setSort={setSort}>Price</Th>
                    <Th k="pe" sort={sort} setSort={setSort}>P/E</Th>
                    <Th k="peg" sort={sort} setSort={setSort}>PEG</Th>
                    <Th k="div" sort={sort} setSort={setSort}>Div</Th>
                    <Th k="roe" sort={sort} setSort={setSort}>ROE</Th>
                    <Th k="rev" sort={sort} setSort={setSort}>Rev gr.</Th>
                    <Th k="value" sort={sort} setSort={setSort}>Value</Th>
                    <Th k="growth" sort={sort} setSort={setSort}>Growth</Th>
                    <Th k="composite" sort={sort} setSort={setSort}>Score</Th>
                    <Th w={36}></Th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((c) => (
                    <tr key={c.ticker} className="row" onClick={() => go("company", c.ticker)}
                      style={{ height: 44, borderBottom: "1px solid var(--border)", cursor: "pointer" }}>
                      <Td align="left">
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <Mono ticker={c.ticker} size={28} />
                          <div>
                            <div className="mono" style={{ fontWeight: 600 }}>{c.ticker}</div>
                            <div style={{ fontSize: 11, color: "var(--text-3)", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>{c.name}</div>
                          </div>
                        </div>
                      </Td>
                      <Td><span className="mono tnum">{fmt.price(c.price)}</span></Td>
                      <Td><span className="mono tnum">{fmt.num(c.pe, 1)}</span></Td>
                      <Td><span className="mono tnum" style={{ color: c.peg && c.peg < 1.5 ? "var(--up)" : "var(--text-2)" }}>{c.peg ? fmt.num(c.peg, 1) : "—"}</span></Td>
                      <Td><span className="mono tnum" style={{ color: "var(--text-2)" }}>{c.divYield ? fmt.pctPlain(c.divYield) : "—"}</span></Td>
                      <Td><span className="mono tnum" style={{ color: "var(--text-2)" }}>{fmt.pctPlain(c.roe)}</span></Td>
                      <Td><span className="mono tnum" style={{ color: c.revGrowth > 0 ? "var(--up)" : "var(--down)" }}>{fmt.pct(c.revGrowth, 0)}</span></Td>
                      <Td align="center"><ScorePip score={c.scores?.value} /></Td>
                      <Td align="center"><ScorePip score={c.scores?.growth} /></Td>
                      <Td><div style={{ display: "flex", justifyContent: "flex-end" }}><CompositeMini score={c.scores?.composite} /></div></Td>
                      <Td>
                        <button title={watch.includes(c.ticker) ? "On watchlist" : "Add to watchlist"}
                          onClick={(e) => { e.stopPropagation(); toggleWatch(c.ticker); }}
                          style={{ color: watch.includes(c.ticker) ? "var(--up)" : "var(--text-3)", display: "grid", placeItems: "center", width: 24, height: 24 }}>
                          <Icon name={watch.includes(c.ticker) ? "check" : "plus"} size={14} />
                        </button>
                      </Td>
                    </tr>
                  ))}
                  {results.length === 0 && (
                    <tr><td colSpan={11} style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>No companies match these filters. Loosen a constraint.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        <style>{`.row:hover{background:var(--surface-hover)}`}</style>
      </div>
    </div>
  );
}

function FilterSlider({ def, value, onChange, onClear }) {
  const active = value != null;
  const val = value == null ? (def.cmp === "lte" ? def.max : def.min) : value;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 12, color: active ? "var(--text)" : "var(--text-2)", fontWeight: active ? 600 : 400 }}>{def.label}</span>
        <span className="mono tnum" style={{ fontSize: 12, color: active ? "var(--accent)" : "var(--text-3)", display: "flex", gap: 6, alignItems: "center" }}>
          {active ? val + def.unit : "any"}
          {active && <button onClick={onClear} style={{ color: "var(--text-3)", display: "grid", placeItems: "center" }}><Icon name="x" size={11} /></button>}
        </span>
      </div>
      <input type="range" min={def.min} max={def.max} step={def.step} value={val}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: "var(--accent)", height: 4, cursor: "pointer" }} />
    </div>
  );
}

/* =================== COMPARE =================== */
const CMP_ROWS = [
  { group: "Price", rows: [
    { label: "Price", get: (c) => c.price, fmt: (v) => fmt.price(v) },
    { label: "Chg today", get: (c) => c.change, render: (c) => <Delta value={c.change} pct />, better: "high" },
    { label: "Market cap", get: (c) => c.marketCap, fmt: (v) => fmt.cap(v), better: "high" },
    { label: "Beta", get: (c) => c.beta, fmt: (v) => fmt.num(v, 2) },
  ]},
  { group: "Valuation", rows: [
    { label: "P/E (ttm)", get: (c) => c.pe, fmt: (v) => fmt.num(v, 1), better: "low" },
    { label: "Forward P/E", get: (c) => c.fwdPe, fmt: (v) => fmt.num(v, 1), better: "low" },
    { label: "PEG", get: (c) => c.peg, fmt: (v) => v ? fmt.num(v, 1) : "—", better: "low" },
    { label: "P/B", get: (c) => c.pb, fmt: (v) => fmt.num(v, 1), better: "low" },
    { label: "P/S", get: (c) => c.ps, fmt: (v) => fmt.num(v, 1), better: "low" },
    { label: "EV/EBITDA", get: (c) => c.evEbitda, fmt: (v) => v ? fmt.num(v, 1) : "—", better: "low" },
    { label: "FCF yield", get: (c) => c.fcfYield, fmt: (v) => v ? fmt.pctPlain(v) : "—", better: "high" },
    { label: "Div yield", get: (c) => c.divYield, fmt: (v) => v ? fmt.pctPlain(v) : "—", better: "high" },
  ]},
  { group: "Profitability & growth", rows: [
    { label: "ROE", get: (c) => c.roe, fmt: (v) => fmt.pctPlain(v), better: "high" },
    { label: "Gross margin", get: (c) => c.grossMargin, fmt: (v) => v ? fmt.pctPlain(v) : "—", better: "high" },
    { label: "Net margin", get: (c) => c.netMargin, fmt: (v) => fmt.pctPlain(v), better: "high" },
    { label: "Rev growth", get: (c) => c.revGrowth, fmt: (v) => fmt.pct(v, 1), better: "high" },
    { label: "EPS growth", get: (c) => c.epsGrowth, fmt: (v) => fmt.pct(v, 1), better: "high" },
    { label: "Debt / equity", get: (c) => c.debtEq, fmt: (v) => fmt.num(v, 2), better: "low" },
  ]},
];

function Compare({ go, set, setSet }) {
  const [adding, setAdding] = useState(false);
  const { loading, error, data } = useAsync(
    () => (set.length ? api.companies(set) : Promise.resolve([])), [set.join(",")]);
  const cos = data || [];
  const remove = (t) => setSet((s) => s.filter((x) => x !== t));
  const add = (t) => { setSet((s) => (s.includes(t) ? s : [...s, t]).slice(0, 5)); setAdding(false); };

  const bestIdx = (row) => {
    if (!row.better) return -1;
    let best = -1, bestV = row.better === "low" ? Infinity : -Infinity;
    cos.forEach((c, i) => {
      const v = row.get(c);
      if (v == null) return;
      if (row.better === "low" ? v < bestV : v > bestV) { bestV = v; best = i; }
    });
    return best;
  };

  const colW = `minmax(120px, 1fr)`;
  const grid = `200px repeat(${cos.length}, ${colW})`;

  return (
    <div className="fade-up" style={{ padding: 24, height: "100%", overflow: "auto" }}>
      <PageHead title="Compare" sub={`${cos.length} companies side by side · best value per metric highlighted`} />

      {loading ? <Loading /> : error ? <ErrorBox error={error} /> : (
      <Card pad={0} style={{ minWidth: "fit-content" }}>
        {/* header row: companies */}
        <div style={{ display: "grid", gridTemplateColumns: grid, position: "sticky", top: 0, background: "var(--surface)", zIndex: 2, borderBottom: "1px solid var(--border)" }}>
          <div style={{ padding: 16, fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-3)", display: "flex", alignItems: "flex-end" }}>Metric</div>
          {cos.map((c) => (
            <div key={c.ticker} style={{ padding: 16, borderLeft: "1px solid var(--border)", position: "relative" }}>
              <button onClick={() => remove(c.ticker)} style={{ position: "absolute", top: 8, right: 8, color: "var(--text-3)", display: "grid", placeItems: "center", width: 20, height: 20 }}><Icon name="x" size={12} /></button>
              <div onClick={() => go("company", c.ticker)} style={{ cursor: "pointer" }}>
                <Mono ticker={c.ticker} size={30} />
                <div className="mono" style={{ fontWeight: 600, marginTop: 8 }}>{c.ticker}</div>
                <div style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</div>
              </div>
              <div style={{ marginTop: 8 }}><ScoreRing score={c.scores?.composite} size={46} stroke={5} showLabel={false} /></div>
            </div>
          ))}
          {cos.length < 5 && (
            <div style={{ padding: 16, borderLeft: "1px solid var(--border)", display: "grid", placeItems: "center", position: "relative" }}>
              <button onClick={() => setAdding((a) => !a)} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, color: "var(--text-3)" }}>
                <div style={{ width: 30, height: 30, borderRadius: 7, border: "1.5px dashed var(--border-strong)", display: "grid", placeItems: "center" }}><Icon name="plus" size={16} /></div>
                <span style={{ fontSize: 11 }}>Add</span>
              </button>
              {adding && <AddSearch onPick={add} exclude={set} />}
            </div>
          )}
        </div>

        {/* metric rows */}
        {CMP_ROWS.map((g) => (
          <div key={g.group}>
            <div style={{ display: "grid", gridTemplateColumns: grid, background: "var(--bg-2)", borderBottom: "1px solid var(--border)" }}>
              <div style={{ gridColumn: `1 / -1`, padding: "7px 16px", fontSize: 10.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-2)" }}>{g.group}</div>
            </div>
            {g.rows.map((row) => {
              const bi = bestIdx(row);
              return (
                <div key={row.label} style={{ display: "grid", gridTemplateColumns: grid, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ padding: "10px 16px", fontSize: 12.5, color: "var(--text-2)" }}>{row.label}</div>
                  {cos.map((c, i) => (
                    <div key={c.ticker} style={{ padding: "10px 16px", borderLeft: "1px solid var(--border)",
                      background: i === bi ? "var(--up-bg)" : "transparent",
                      display: "flex", alignItems: "center", gap: 6 }}>
                      {row.render ? row.render(c) : <span className="mono tnum" style={{ fontSize: 13, fontWeight: i === bi ? 600 : 400, color: i === bi ? "var(--up)" : "var(--text)" }}>{row.fmt(row.get(c))}</span>}
                      {i === bi && !row.render && <Icon name="check" size={11} style={{ color: "var(--up)" }} />}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        ))}

        {/* scores row */}
        <div style={{ display: "grid", gridTemplateColumns: grid, background: "var(--bg-2)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ gridColumn: `1 / -1`, padding: "7px 16px", fontSize: 10.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-2)" }}>Scores</div>
        </div>
        {["value", "growth", "health", "momentum", "composite"].map((sk) => {
          let best = -1, bestV = -Infinity;
          cos.forEach((c, i) => { const v = c.scores?.[sk]; if (v != null && v > bestV) { bestV = v; best = i; } });
          return (
            <div key={sk} style={{ display: "grid", gridTemplateColumns: grid, borderBottom: "1px solid var(--border)" }}>
              <div style={{ padding: "10px 16px", fontSize: 12.5, color: "var(--text-2)", textTransform: "capitalize", fontWeight: sk === "composite" ? 600 : 400 }}>{sk}</div>
              {cos.map((c, i) => (
                <div key={c.ticker} style={{ padding: "10px 16px", borderLeft: "1px solid var(--border)", background: i === best ? "var(--up-bg)" : "transparent" }}>
                  <CompositeMini score={c.scores?.[sk]} />
                </div>
              ))}
            </div>
          );
        })}
      </Card>
      )}
    </div>
  );
}

/* buscador para añadir empresas a Compare (sustituye el dropdown del universo completo) */
function AddSearch({ onPick, exclude }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (!q.trim()) { setRes([]); return; }
    const id = setTimeout(() => {
      api.search(q.trim()).then((r) => setRes(r.filter((x) => !exclude.includes(x.ticker)))).catch(() => setRes([]));
    }, 200);
    return () => clearTimeout(id);
  }, [q, exclude]);
  return (
    <div style={{ position: "absolute", top: 70, left: 8, right: 8, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, boxShadow: "var(--shadow)", padding: 5, zIndex: 10, maxHeight: 260, overflowY: "auto" }}>
      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar ticker o nombre…"
        style={{ width: "100%", boxSizing: "border-box", padding: "6px 8px", marginBottom: 4, border: "1px solid var(--border)", borderRadius: 6, background: "var(--surface-2)", color: "var(--text)", fontSize: 12, outline: "none" }} />
      {res.map((c) => (
        <div key={c.ticker} onMouseDown={() => onPick(c.ticker)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: 6, cursor: "pointer" }}
          onMouseEnter={(e) => e.currentTarget.style.background = "var(--surface-hover)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
          <Mono ticker={c.ticker} size={22} />
          <span className="mono" style={{ fontWeight: 600, fontSize: 12 }}>{c.ticker}</span>
          <span style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</span>
        </div>
      ))}
    </div>
  );
}

export { Screener, Compare, FilterSlider };
