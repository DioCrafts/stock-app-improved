/* ============================================================
   screens-watchlist-overview.jsx — Watchlist + Company ficha
   ============================================================ */
import { useState } from "react";
import { api, useAsync } from "../api.js";
import {
  fmt, scoreColor, scoreLabel, Icon, Mono, Delta, Sparkline, AreaChart,
  ScoreRing, ScoreBar, Pill, Card, Stat,
} from "../components/ui.jsx";
import { Th, Td, ScorePip, CompositeMini, PageHead, Loading, ErrorBox, Empty } from "../components/shared.jsx";

/* =================== WATCHLIST =================== */
function Watchlist({ go, watch, toggleWatch }) {
  const [sort, setSort] = useState({ k: "composite", dir: "desc" });
  const { loading, error, data } = useAsync(
    () => (watch.length ? api.companies(watch) : Promise.resolve([])), [watch.join(",")]);
  const rows = data || [];

  const sorted = [...rows].sort((a, b) => {
    const get = (c) => ({
      ticker: c.ticker, price: c.price, change: c.change, cap: c.marketCap ?? -1,
      pe: c.pe ?? 1e9, peg: c.peg ?? 1e9, div: c.divYield ?? -1,
      value: c.scores?.value ?? -1, growth: c.scores?.growth ?? -1, composite: c.scores?.composite ?? -1,
    }[sort.k]);
    const av = get(a), bv = get(b);
    if (typeof av === "string") return sort.dir === "desc" ? bv.localeCompare(av) : av.localeCompare(bv);
    return sort.dir === "desc" ? bv - av : av - bv;
  });

  const withComp = rows.filter((c) => c.scores?.composite != null);
  const avgScore = withComp.length ? Math.round(withComp.reduce((s, c) => s + c.scores.composite, 0) / withComp.length) : null;
  const best = rows.length ? [...rows].sort((a, b) => (b.change ?? -1e9) - (a.change ?? -1e9))[0] : null;
  const worst = rows.length ? [...rows].sort((a, b) => (a.change ?? 1e9) - (b.change ?? 1e9))[0] : null;
  const gainers = rows.filter((c) => c.change > 0).length;

  return (
    <div className="fade-up" style={{ padding: 24, height: "100%", overflowY: "auto" }}>
      <PageHead title="Watchlist" sub={`${rows.length} companies tracked · NYSE / NASDAQ / TSX / LSE`} />

      {loading ? <Loading /> : error ? <ErrorBox error={error} /> : rows.length === 0 ? (
        <Empty label="Tu watchlist está vacía. Añade empresas desde el Screener o la búsqueda." />
      ) : (
        <>
          {/* summary strip */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 18 }}>
            <SummaryTile label="Avg composite score" value={avgScore} ring />
            <SummaryTile label="Advancing today" value={`${gainers}/${rows.length}`} sub={`${rows.length - gainers} declining`} />
            <SummaryTile label="Top mover" value={best ? best.ticker : "—"} delta={best ? best.change : null} onClick={best ? () => go("company", best.ticker) : null} />
            <SummaryTile label="Laggard" value={worst ? worst.ticker : "—"} delta={worst ? worst.change : null} onClick={worst ? () => go("company", worst.ticker) : null} />
          </div>

          <Card pad={0}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <Th k="ticker" sort={sort} setSort={setSort} align="left">Company</Th>
                    <Th k="price" sort={sort} setSort={setSort}>Price</Th>
                    <Th k="change" sort={sort} setSort={setSort}>Chg</Th>
                    <Th k="cap" sort={sort} setSort={setSort}>Mkt Cap</Th>
                    <Th k="pe" sort={sort} setSort={setSort}>P/E</Th>
                    <Th k="peg" sort={sort} setSort={setSort}>PEG</Th>
                    <Th k="div" sort={sort} setSort={setSort}>Div</Th>
                    <Th k="value" sort={sort} setSort={setSort}>Value</Th>
                    <Th k="growth" sort={sort} setSort={setSort}>Growth</Th>
                    <Th k="composite" sort={sort} setSort={setSort}>Score</Th>
                    <Th w={36}></Th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((c) => (
                    <tr key={c.ticker} className="row"
                      onClick={() => go("company", c.ticker)}
                      style={{ height: 46, borderBottom: "1px solid var(--border)", cursor: "pointer" }}>
                      <Td align="left">
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <Mono ticker={c.ticker} size={30} />
                          <div style={{ minWidth: 0 }}>
                            <div className="mono" style={{ fontWeight: 600, fontSize: 13 }}>{c.ticker}</div>
                            <div style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 150 }}>{c.name}</div>
                          </div>
                        </div>
                      </Td>
                      <Td><span className="mono tnum">{fmt.price(c.price)}</span></Td>
                      <Td><Delta value={c.change} pct /></Td>
                      <Td><span className="mono tnum" style={{ color: "var(--text-2)" }}>{fmt.cap(c.marketCap)}</span></Td>
                      <Td><span className="mono tnum">{fmt.num(c.pe, 1)}</span></Td>
                      <Td><span className="mono tnum" style={{ color: c.peg && c.peg < 1.5 ? "var(--up)" : "var(--text-2)" }}>{c.peg ? fmt.num(c.peg, 1) : "—"}</span></Td>
                      <Td><span className="mono tnum" style={{ color: "var(--text-2)" }}>{c.divYield ? fmt.pctPlain(c.divYield) : "—"}</span></Td>
                      <Td align="center"><ScorePip score={c.scores?.value} /></Td>
                      <Td align="center"><ScorePip score={c.scores?.growth} /></Td>
                      <Td><div style={{ display: "flex", justifyContent: "flex-end" }}><CompositeMini score={c.scores?.composite} /></div></Td>
                      <Td>
                        <button title="Remove" onClick={(e) => { e.stopPropagation(); toggleWatch(c.ticker); }}
                          style={{ color: "var(--text-3)", display: "grid", placeItems: "center", width: 24, height: 24, borderRadius: 5 }}
                          onMouseEnter={(e) => e.currentTarget.style.color = "var(--down)"}
                          onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-3)"}>
                          <Icon name="x" size={13} />
                        </button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 12 }}>
            Click any row to open the company. Scores: Value 35% · Growth 30% · Health 20% · Momentum 15% (percentiles por mercado).
          </p>
        </>
      )}
      <style>{`.row:hover{background:var(--surface-hover)}`}</style>
    </div>
  );
}

function SummaryTile({ label, value, sub, delta, ring, onClick }) {
  return (
    <div onClick={onClick} style={{
      background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)",
      padding: "14px 16px", display: "flex", alignItems: "center", justifyContent: "space-between",
      cursor: onClick ? "pointer" : "default",
    }}>
      <div>
        <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>{label}</div>
        <div className="mono tnum" style={{ fontSize: 22, fontWeight: 600 }}>{value ?? "—"}</div>
        {sub && <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>{sub}</div>}
        {delta != null && <div style={{ marginTop: 2 }}><Delta value={delta} pct /></div>}
      </div>
      {ring && <ScoreRing score={typeof value === "number" ? value : null} size={52} stroke={5} showLabel={false} />}
    </div>
  );
}

/* =================== COMPANY OVERVIEW =================== */
const RANGE_DAYS = { "1M": 22, "3M": 63, "6M": 126, "1Y": 252 };

function CompanyOverview({ ticker, go, watch, toggleWatch }) {
  const [range, setRange] = useState("3M");
  const { loading, error, data: c } = useAsync(() => api.company(ticker), [ticker]);
  const pricesState = useAsync(() => api.prices(ticker, "1Y"), [ticker]);

  if (loading) return <div className="fade-up" style={{ padding: 24 }}><Loading /></div>;
  if (error || !c) return <div className="fade-up" style={{ padding: 24 }}><ErrorBox error={error} label="Empresa no encontrada" /></div>;

  const watched = watch.includes(c.ticker);
  const closes = (pricesState.data?.points || []).map((p) => p.close);
  const series = closes.slice(-RANGE_DAYS[range]);
  const lo = closes.length ? Math.min(...closes) : null;
  const hi = closes.length ? Math.max(...closes) : null;

  const statGroups = [
    { title: "Valuation", items: [
      ["Market cap", fmt.cap(c.marketCap)], ["P/E (ttm)", fmt.num(c.pe, 1)],
      ["Forward P/E", fmt.num(c.fwdPe, 1)], ["PEG", c.peg ? fmt.num(c.peg, 1) : "—"],
      ["P/B", fmt.num(c.pb, 1)], ["P/S", fmt.num(c.ps, 1)],
      ["EV/EBITDA", c.evEbitda ? fmt.num(c.evEbitda, 1) : "—"], ["FCF yield", c.fcfYield ? fmt.pctPlain(c.fcfYield) : "—"],
    ]},
    { title: "Profitability", items: [
      ["ROE", fmt.pctPlain(c.roe)], ["ROIC", c.roic ? fmt.pctPlain(c.roic) : "—"],
      ["Gross margin", c.grossMargin ? fmt.pctPlain(c.grossMargin) : "—"], ["Oper. margin", fmt.pctPlain(c.opMargin)],
      ["Net margin", fmt.pctPlain(c.netMargin)], ["Div yield", c.divYield ? fmt.pctPlain(c.divYield) : "—"],
    ]},
    { title: "Growth & risk", items: [
      ["Revenue growth", fmt.pct(c.revGrowth, 1)], ["EPS growth", fmt.pct(c.epsGrowth, 1)],
      ["Debt / equity", fmt.num(c.debtEq, 2)], ["Current ratio", c.currentRatio ? fmt.num(c.currentRatio, 2) : "—"],
      ["Beta", fmt.num(c.beta, 2)], ["Employees", c.employees ? (c.employees / 1000).toFixed(0) + "k" : "—"],
    ]},
  ];

  return (
    <div className="fade-up" style={{ padding: 24, height: "100%", overflowY: "auto" }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <Mono ticker={c.ticker} size={52} />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
            <h1 className="mono" style={{ fontSize: 24, fontWeight: 600 }}>{c.ticker}</h1>
            <span style={{ fontSize: 15, color: "var(--text-2)" }}>{c.name}</span>
            <Pill>{c.exchange}</Pill>
            <Pill>{c.sector}</Pill>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 8 }}>
            <span className="mono tnum" style={{ fontSize: 30, fontWeight: 600 }}>{fmt.price(c.price)}</span>
            <Delta value={c.change} pct size={16} />
            <span className="mono tnum" style={{ fontSize: 13, color: "var(--text-3)" }}>
              {fmt.signed(c.price - c.prevClose)} today
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <ActionBtn icon="valuation" label="DCF" onClick={() => go("valuation", c.ticker)} />
          <ActionBtn icon="financials" label="Financials" onClick={() => go("financials", c.ticker)} />
          <ActionBtn icon="compare" label="Compare" onClick={() => go("compare", c.ticker)} />
          <ActionBtn icon={watched ? "check" : "plus"} label={watched ? "Watching" : "Watch"}
            primary={!watched} active={watched} onClick={() => toggleWatch(c.ticker)} />
        </div>
      </div>

      {/* main grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16, alignItems: "start" }}>
        {/* left: chart + stats */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card title="Price" pad={16}
            action={<div style={{ display: "flex", gap: 4 }}>
              {Object.keys(RANGE_DAYS).map((r) => (
                <button key={r} onClick={() => setRange(r)} className="mono"
                  style={{
                    fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 5,
                    color: range === r ? "var(--text)" : "var(--text-3)",
                    background: range === r ? "var(--surface-2)" : "transparent",
                  }}>{r}</button>
              ))}
            </div>}>
            {pricesState.loading ? <Loading /> : series.length < 2 ? <Empty label="Sin datos de precio" /> : <AreaChart data={series} h={250} baseline={series[0]} />}
          </Card>

          {statGroups.map((g) => (
            <Card key={g.title} title={g.title} pad={0}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)" }}>
                {g.items.map(([label, val], i) => (
                  <div key={label} style={{
                    padding: "13px 16px",
                    borderRight: (i % 4 !== 3) ? "1px solid var(--border)" : "none",
                    borderTop: i >= 4 ? "1px solid var(--border)" : "none",
                  }}>
                    <Stat label={label} value={val} />
                  </div>
                ))}
              </div>
            </Card>
          ))}

          <Card title="About" pad={16}>
            <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6, textWrap: "pretty" }}>{c.desc || "—"}</p>
          </Card>
        </div>

        {/* right: score panel + revenue */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, position: "sticky", top: 0 }}>
          <Card title="Composite score" pad={16}>
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 18 }}>
              <ScoreRing score={c.scores?.composite} size={84} stroke={8} />
              <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.5 }}>
                {c.scores?.composite != null ? (
                  <><strong style={{ color: scoreColor(c.scores.composite) }}>{scoreLabel(c.scores.composite)}</strong> overall. </>
                ) : null}
                Weighted blend of value, growth, balance-sheet health and price momentum.
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <ScoreBar label="Value" sub="ratios" score={c.scores?.value} />
              <ScoreBar label="Growth" sub="rev, EPS" score={c.scores?.growth} />
              <ScoreBar label="Health" sub="balance" score={c.scores?.health} />
              <ScoreBar label="Momentum" sub="price" score={c.scores?.momentum} />
            </div>
          </Card>

          <Card title="Revenue ($B)" pad={16}>
            {c.revenue && c.revenue.length ? <RevenueBars data={c.revenue} years={c.revenueYears} /> : <Empty label="Sin datos" />}
          </Card>

          <Card title="Snapshot" pad={0}>
            <KV k="52-wk range" v={`${fmt.price(lo)} – ${fmt.price(hi)}`} />
            <KV k="Prev close" v={fmt.price(c.prevClose)} />
            <KV k="Market cap" v={fmt.cap(c.marketCap)} />
            <KV k="Dividend yield" v={c.divYield ? fmt.pctPlain(c.divYield) : "None"} last />
          </Card>
        </div>
      </div>
    </div>
  );
}

function KV({ k, v, last }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "11px 16px", borderBottom: last ? "none" : "1px solid var(--border)" }}>
      <span style={{ fontSize: 12, color: "var(--text-3)" }}>{k}</span>
      <span className="mono tnum" style={{ fontSize: 12.5, fontWeight: 500 }}>{v}</span>
    </div>
  );
}

function ActionBtn({ icon, label, onClick, primary, active }) {
  return (
    <button onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 13px",
      borderRadius: "var(--r-md)", fontSize: 12.5, fontWeight: 600,
      background: primary ? "var(--accent)" : active ? "var(--up-bg)" : "var(--surface)",
      color: primary ? "white" : active ? "var(--up)" : "var(--text-2)",
      border: "1px solid " + (primary ? "transparent" : active ? "transparent" : "var(--border)"),
    }}>
      <Icon name={icon} size={15} /> {label}
    </button>
  );
}

function RevenueBars({ data, years }) {
  const max = Math.max(...data);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 130 }}>
      {data.map((v, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%", justifyContent: "flex-end" }}>
          <span className="mono tnum" style={{ fontSize: 10.5, color: "var(--text-2)", fontWeight: 500 }}>{v < 100 ? v.toFixed(0) : Math.round(v)}</span>
          <div style={{
            width: "100%", maxWidth: 30, height: (v / max) * 90 + "px", borderRadius: "4px 4px 0 0",
            background: i === data.length - 1 ? "var(--accent)" : "var(--accent-bg)",
            border: "1px solid var(--accent)",
            borderBottom: "none", transition: "height .4s ease",
          }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--text-3)" }}>{years && years[i] != null ? "'" + String(years[i]).slice(2) : ""}</span>
        </div>
      ))}
    </div>
  );
}

export { Watchlist, CompanyOverview };
