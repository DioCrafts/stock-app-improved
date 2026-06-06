/* ============================================================
   app.jsx — shell: sidebar nav, global search, theme, routing
   ============================================================ */
import { useState, useEffect, useRef } from "react";
import { api, useAsync } from "./api.js";
import { Icon, Mono, Delta, fmt } from "./components/ui.jsx";
import { Watchlist, CompanyOverview } from "./screens/WatchlistOverview.jsx";
import { CompositeMini } from "./components/shared.jsx";
import { Screener, Compare } from "./screens/ScreenerCompare.jsx";
import { Valuation, Financials } from "./screens/ValuationFinancials.jsx";

function useLocalState(key, init) {
  const [v, setV] = useState(() => {
    try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : init; } catch { return init; }
  });
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)); } catch {} }, [key, v]);
  return [v, setV];
}

// Watchlist inicial (semilla de localStorage); el estado de usuario vive en el navegador.
const DEFAULT_WATCH = ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "JPM", "V"];

const NAV = [
  { id: "watchlist", icon: "watchlist", label: "Watchlist" },
  { id: "screener", icon: "screener", label: "Screener" },
  { id: "compare", icon: "compare", label: "Compare" },
  { id: "valuation", icon: "valuation", label: "Valuation" },
  { id: "financials", icon: "financials", label: "Financials" },
];

function GlobalSearch({ go }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const [results, setResults] = useState([]);
  const ref = useRef(null);

  // búsqueda server-side con debounce
  useEffect(() => {
    if (!q.trim()) { setResults([]); return; }
    const id = setTimeout(() => {
      api.search(q.trim()).then((r) => setResults(r)).catch(() => setResults([]));
    }, 200);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); ref.current?.focus(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  const pick = (c) => { go("company", c.ticker); setQ(""); setOpen(false); ref.current?.blur(); };
  return (
    <div style={{ position: "relative", width: 360, maxWidth: "40vw" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 12px", height: 38,
        background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r-md)" }}>
        <Icon name="search" size={16} style={{ color: "var(--text-3)" }} />
        <input ref={ref} value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setHi(0); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setHi((h) => Math.min(h + 1, results.length - 1));
            if (e.key === "ArrowUp") setHi((h) => Math.max(h - 1, 0));
            if (e.key === "Enter" && results[hi]) pick(results[hi]);
            if (e.key === "Escape") { setOpen(false); ref.current?.blur(); }
          }}
          placeholder="Search ticker or company…"
          style={{ flex: 1, border: "none", outline: "none", background: "transparent", color: "var(--text)", fontSize: 13 }} />
        <kbd className="mono" style={{ fontSize: 10, color: "var(--text-3)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px" }}>⌘K</kbd>
      </div>
      {open && results.length > 0 && (
        <div style={{ position: "absolute", top: 44, left: 0, right: 0, background: "var(--surface)",
          border: "1px solid var(--border)", borderRadius: "var(--r-md)", boxShadow: "var(--shadow)", padding: 5, zIndex: 50 }}>
          {results.map((c, i) => (
            <div key={c.ticker} onMouseDown={() => pick(c)} onMouseEnter={() => setHi(i)}
              style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 9px", borderRadius: 6,
                cursor: "pointer", background: i === hi ? "var(--surface-hover)" : "transparent" }}>
              <Mono ticker={c.ticker} size={26} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span className="mono" style={{ fontWeight: 600 }}>{c.ticker}</span>
                <span style={{ fontSize: 12, color: "var(--text-3)", marginLeft: 8 }}>{c.name}</span>
              </div>
              <span className="mono tnum" style={{ fontSize: 12 }}>{fmt.price(c.price)}</span>
              <div style={{ width: 44 }}>{c.composite != null && <CompositeMini score={c.composite} />}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function App() {
  const [route, setRoute] = useLocalState("term.route", { screen: "watchlist", ticker: "NVDA" });
  const [theme, setTheme] = useLocalState("term.theme", "dark");
  const [watch, setWatch] = useLocalState("term.watch", DEFAULT_WATCH);
  const [compareSet, setCompareSet] = useLocalState("term.compare", ["NVDA", "MSFT", "GOOGL", "META"]);

  // datos del shell (índices, estado de mercado, watchlist del sidebar)
  const { data: indices } = useAsync(() => api.indices(), []);
  const { data: marketStatus } = useAsync(() => api.marketStatus(), []);
  const { data: watchCos } = useAsync(() => (watch.length ? api.companies(watch) : Promise.resolve([])), [watch.join(",")]);
  const watchByTicker = {};
  (watchCos || []).forEach((c) => { watchByTicker[c.ticker] = c; });

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const go = (screen, ticker) => {
    if (screen === "compare" && ticker) {
      setCompareSet((s) => s.includes(ticker) ? s : [...s, ticker].slice(0, 5));
    }
    setRoute({ screen, ticker: ticker || route.ticker });
  };
  const toggleWatch = (t) => setWatch((w) => w.includes(t) ? w.filter((x) => x !== t) : [...w, t]);

  const screenEl = (() => {
    switch (route.screen) {
      case "watchlist": return <Watchlist go={go} watch={watch} toggleWatch={toggleWatch} />;
      case "company": return <CompanyOverview ticker={route.ticker} go={go} watch={watch} toggleWatch={toggleWatch} />;
      case "screener": return <Screener go={go} watch={watch} toggleWatch={toggleWatch} />;
      case "compare": return <Compare go={go} set={compareSet} setSet={setCompareSet} />;
      case "valuation": return <Valuation ticker={route.ticker} go={go} />;
      case "financials": return <Financials ticker={route.ticker} go={go} />;
      default: return null;
    }
  })();

  // which nav item is "active"
  const activeNav = route.screen === "company" ? null : route.screen;

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* sidebar */}
      <aside style={{ width: 212, flex: "none", background: "var(--bg-2)", borderRight: "1px solid var(--border)",
        display: "flex", flexDirection: "column", padding: "16px 12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "4px 8px 18px" }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: "var(--accent)", display: "grid", placeItems: "center" }}>
            <Icon name="bolt" size={17} fill style={{ color: "white" }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, letterSpacing: "-0.01em" }}>Terminal</div>
            <div style={{ fontSize: 10, color: "var(--text-3)", letterSpacing: "0.04em" }}>EQUITY RESEARCH</div>
          </div>
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {NAV.map((n) => {
            const active = activeNav === n.id;
            return (
              <button key={n.id} onClick={() => go(n.id, n.id === "valuation" || n.id === "financials" ? route.ticker : undefined)}
                style={{ display: "flex", alignItems: "center", gap: 11, padding: "9px 11px", borderRadius: "var(--r-md)",
                  fontSize: 13, fontWeight: 500, textAlign: "left",
                  color: active ? "var(--text)" : "var(--text-2)",
                  background: active ? "var(--surface)" : "transparent",
                  boxShadow: active ? "var(--shadow)" : "none",
                  border: "1px solid " + (active ? "var(--border)" : "transparent") }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--surface-2)"; }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}>
                <span style={{ color: active ? "var(--accent)" : "var(--text-3)" }}><Icon name={n.icon} size={18} /></span>
                {n.label}
              </button>
            );
          })}
        </nav>

        <div style={{ marginTop: 18, padding: "0 11px" }}>
          <div style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Watchlist</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {watch.slice(0, 6).map((t) => {
              const c = watchByTicker[t];
              return (
                <button key={t} onClick={() => go("company", t)}
                  style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "5px 6px", borderRadius: 6, fontSize: 12 }}
                  onMouseEnter={(e) => e.currentTarget.style.background = "var(--surface-2)"}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                  <span className="mono" style={{ fontWeight: 600 }}>{t}</span>
                  <Delta value={c ? c.change : null} pct arrow={false} size={11} />
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px" }}>
          <ThemeToggle theme={theme} setTheme={setTheme} />
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-3)" }}>
            <span className="live-dot"></span> {marketStatus?.open ? "Market open" : "Market closed"}
          </div>
        </div>
      </aside>

      {/* main column */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header style={{ height: 56, flex: "none", borderBottom: "1px solid var(--border)", background: "var(--bg)",
          display: "flex", alignItems: "center", gap: 16, padding: "0 24px" }}>
          <GlobalSearch go={go} />
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 18 }}>
            {(indices || []).map((ix) => (
              <IndexChip key={ix.symbol} label={ix.label}
                value={ix.value.toLocaleString("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}
                chg={ix.change} invert={ix.symbol === "^VIX"} />
            ))}
          </div>
        </header>
        <main style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>{screenEl}</main>
      </div>
    </div>
  );
}

function IndexChip({ label, value, chg, invert }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.25 }}>
      <div style={{ fontSize: 10, color: "var(--text-3)", letterSpacing: "0.04em" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span className="mono tnum" style={{ fontSize: 12.5, fontWeight: 600 }}>{value}</span>
        <Delta value={chg} pct arrow={false} size={11} />
      </div>
    </div>
  );
}

function ThemeToggle({ theme, setTheme }) {
  const dark = theme === "dark";
  return (
    <button onClick={() => setTheme(dark ? "light" : "dark")}
      style={{ display: "flex", alignItems: "center", gap: 7, padding: "6px 10px", borderRadius: 999,
        background: "var(--surface)", border: "1px solid var(--border)", fontSize: 12, color: "var(--text-2)", fontWeight: 500 }}>
      <Icon name={dark ? "moon" : "sun"} size={15} /> {dark ? "Dark" : "Light"}
    </button>
  );
}

export default App;
