/* ============================================================
   screens-valuation-financials.jsx — DCF + Financial statements
   Valuation (interactive DCF) and multi-tab financial statements.
   ============================================================ */
import { useState, useEffect, useMemo } from "react";
import { DATA } from "../data.js";
import { fmt, Icon, Mono, Sparkline, Pill, Card, Stat } from "../components/ui.jsx";
import { PageHead } from "../components/shared.jsx";

/* ---------- shared: company picker dropdown ---------- */
function CompanyPicker({ ticker, onPick }) {
  const [open, setOpen] = useState(false);
  const c = DATA.byTicker[ticker];
  return (
    <div style={{ position: "relative" }}>
      <button onClick={() => setOpen((o) => !o)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 10px 6px 6px", borderRadius: "var(--r-md)",
          background: "var(--surface)", border: "1px solid var(--border)" }}>
        <Mono ticker={c.ticker} size={28} />
        <div style={{ textAlign: "left" }}>
          <div className="mono" style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.1 }}>{c.ticker}</div>
          <div style={{ fontSize: 10.5, color: "var(--text-3)" }}>{c.name}</div>
        </div>
        <Icon name="chevD" size={14} style={{ color: "var(--text-3)", marginLeft: 4 }} />
      </button>
      {open && (
        <div style={{ position: "absolute", top: 50, left: 0, width: 240, background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 8, boxShadow: "var(--shadow)", padding: 5, zIndex: 20, maxHeight: 320, overflowY: "auto" }}>
          {DATA.companies.map((x) => (
            <div key={x.ticker} onMouseDown={() => { onPick(x.ticker); setOpen(false); }}
              style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 8px", borderRadius: 6, cursor: "pointer",
                background: x.ticker === ticker ? "var(--accent-bg)" : "transparent" }}
              onMouseEnter={(e) => { if (x.ticker !== ticker) e.currentTarget.style.background = "var(--surface-hover)"; }}
              onMouseLeave={(e) => { if (x.ticker !== ticker) e.currentTarget.style.background = "transparent"; }}>
              <Mono ticker={x.ticker} size={24} />
              <span className="mono" style={{ fontWeight: 600, fontSize: 12 }}>{x.ticker}</span>
              <span style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{x.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* =================== VALUATION (DCF) =================== */
function Valuation({ ticker, go }) {
  const c = DATA.byTicker[ticker];
  const shares = c.marketCap / c.price; // billions of shares
  const baseFCF = c.fcfYield ? c.marketCap * c.fcfYield / 100 : c.revenue[c.revenue.length - 1] * Math.max(c.netMargin, 5) / 100 * 0.9;
  const defNetDebt = +(c.marketCap * (c.debtEq > 1 ? 0.08 : c.debtEq > 0.4 ? 0.03 : -0.04)).toFixed(1);

  const [inp, setInp] = useState(() => ({
    fcf: +baseFCF.toFixed(1),
    growth: Math.round(Math.max(3, Math.min(c.revGrowth || 8, 25))),
    years: 5,
    terminal: 2.5,
    wacc: Math.round((7 + (c.beta || 1) * 1.4) * 10) / 10,
    netDebt: defNetDebt,
  }));
  const set = (k, v) => setInp((s) => ({ ...s, [k]: v }));
  useEffect(() => {
    setInp({ fcf: +baseFCF.toFixed(1), growth: Math.round(Math.max(3, Math.min(c.revGrowth || 8, 25))),
      years: 5, terminal: 2.5, wacc: Math.round((7 + (c.beta || 1) * 1.4) * 10) / 10, netDebt: defNetDebt });
  }, [ticker]);

  const calc = (wacc, terminal) => {
    const r = wacc / 100, g = terminal / 100, gr = inp.growth / 100;
    let pv = 0; const flows = [];
    for (let t = 1; t <= inp.years; t++) {
      const fcf = inp.fcf * Math.pow(1 + gr, t);
      const disc = fcf / Math.pow(1 + r, t);
      flows.push({ t, fcf, pv: disc });
      pv += disc;
    }
    const last = inp.fcf * Math.pow(1 + gr, inp.years);
    const tv = (last * (1 + g)) / (r - g);
    const pvTv = tv / Math.pow(1 + r, inp.years);
    const ev = pv + pvTv;
    const equity = ev - inp.netDebt;
    const fair = equity / shares;
    return { flows, pv, pvTv, ev, equity, fair, upside: fair / c.price - 1 };
  };
  const res = useMemo(() => calc(inp.wacc, inp.terminal), [inp, ticker]);
  const upPct = res.upside * 100;
  const verdict = upPct > 15 ? { t: "Undervalued", tone: "up" } : upPct < -15 ? { t: "Overvalued", tone: "down" } : { t: "Fairly valued", tone: "neutral" };

  const waccRange = [inp.wacc - 2, inp.wacc - 1, inp.wacc, inp.wacc + 1, inp.wacc + 2];
  const termRange = [Math.max(0.5, inp.terminal - 1), inp.terminal - 0.5, inp.terminal, inp.terminal + 0.5, inp.terminal + 1];

  return (
    <div className="fade-up" style={{ padding: 24, height: "100%", overflowY: "auto" }}>
      <PageHead title="Valuation — DCF"
        sub="Discounted cash-flow model · adjust assumptions, fair value updates live"
        right={<CompanyPicker ticker={ticker} onPick={(t) => go("valuation", t)} />} />

      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 16, alignItems: "start" }}>
        {/* inputs */}
        <Card title="Assumptions" pad={18}>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <DcfInput label="Starting FCF" unit="$B" v={inp.fcf} min={1} max={Math.round(baseFCF * 3) || 100} step={0.5} onChange={(v) => set("fcf", v)} hint="Trailing free cash flow" />
            <DcfInput label="FCF growth (yrs 1–N)" unit="%" v={inp.growth} min={-5} max={40} step={0.5} onChange={(v) => set("growth", v)} hint="Annual growth during forecast" />
            <DcfInput label="Forecast years" unit="" v={inp.years} min={3} max={10} step={1} onChange={(v) => set("years", v)} />
            <DcfInput label="Terminal growth" unit="%" v={inp.terminal} min={0.5} max={4} step={0.1} onChange={(v) => set("terminal", v)} hint="Perpetual growth after forecast" />
            <DcfInput label="Discount rate (WACC)" unit="%" v={inp.wacc} min={5} max={16} step={0.1} onChange={(v) => set("wacc", v)} hint="Required return / cost of capital" />
            <DcfInput label="Net debt" unit="$B" v={inp.netDebt} min={-200} max={400} step={1} onChange={(v) => set("netDebt", v)} hint="Debt minus cash (negative = net cash)" />
          </div>
        </Card>

        {/* output */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card pad={20}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Intrinsic value / share</div>
                <div className="mono tnum" style={{ fontSize: 34, fontWeight: 600, color: `var(--${verdict.tone === "neutral" ? "text" : verdict.tone})` }}>{fmt.price(res.fair)}</div>
                <div style={{ marginTop: 6 }}><Pill tone={verdict.tone === "neutral" ? "accent" : verdict.tone}>{verdict.t}</Pill></div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Current price</div>
                <div className="mono tnum" style={{ fontSize: 34, fontWeight: 600, color: "var(--text-2)" }}>{fmt.price(c.price)}</div>
                <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 8 }}>{c.ticker} · {c.exchange}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Upside / downside</div>
                <div className="mono tnum" style={{ fontSize: 34, fontWeight: 600, color: upPct >= 0 ? "var(--up)" : "var(--down)" }}>{fmt.pct(upPct, 1)}</div>
                {/* gauge */}
                <div style={{ marginTop: 12, height: 8, borderRadius: 4, background: "var(--border)", position: "relative", overflow: "hidden" }}>
                  <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--text-3)", zIndex: 2 }} />
                  <div style={{ position: "absolute", top: 0, bottom: 0,
                    left: upPct >= 0 ? "50%" : `${50 + Math.max(-50, upPct / 2)}%`,
                    width: Math.min(50, Math.abs(upPct) / 2) + "%",
                    background: upPct >= 0 ? "var(--up)" : "var(--down)" }} />
                </div>
              </div>
            </div>
          </Card>

          {/* bridge */}
          <Card title="Enterprise → equity bridge" pad={18}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
              <Stat label="PV of forecast FCF" value={fmt.cap(res.pv)} />
              <Stat label="PV of terminal value" value={fmt.cap(res.pvTv)} sub={`${Math.round(res.pvTv / res.ev * 100)}% of EV`} />
              <Stat label="Enterprise value" value={fmt.cap(res.ev)} />
              <Stat label="Equity value" value={fmt.cap(res.equity)} sub={`− ${fmt.cap(inp.netDebt)} net debt`} />
            </div>
            <div style={{ marginTop: 18 }}>
              <FcfBars flows={res.flows} />
            </div>
          </Card>

          {/* sensitivity */}
          <Card title="Sensitivity — fair value ($/share)" pad={0}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                <thead>
                  <tr>
                    <th style={{ padding: "10px 12px", textAlign: "left", fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em" }}>WACC ↓ / term →</th>
                    {termRange.map((g) => (
                      <th key={g} className="mono" style={{ padding: "10px 12px", textAlign: "right", fontSize: 11, color: "var(--text-2)" }}>{g.toFixed(1)}%</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {waccRange.map((w) => (
                    <tr key={w} style={{ borderTop: "1px solid var(--border)" }}>
                      <td className="mono" style={{ padding: "9px 12px", fontSize: 11, color: "var(--text-2)" }}>{w.toFixed(1)}%</td>
                      {termRange.map((g) => {
                        const f = calc(w, g).fair;
                        const up = f / c.price - 1;
                        const isCur = Math.abs(w - inp.wacc) < 0.01 && Math.abs(g - inp.terminal) < 0.01;
                        return (
                          <td key={g} className="mono tnum" style={{ padding: "9px 12px", textAlign: "right", fontWeight: isCur ? 700 : 400,
                            color: up >= 0 ? "var(--up)" : "var(--down)",
                            background: isCur ? "var(--accent-bg)" : `oklch(${up >= 0 ? "0.72 0.16 155" : "0.66 0.20 25"} / ${Math.min(0.16, Math.abs(up) * 0.4)})`,
                            outline: isCur ? "1px solid var(--accent)" : "none", outlineOffset: -1 }}>
                            {fmt.price(f)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <p style={{ fontSize: 11, color: "var(--text-3)" }}>
            Illustrative model on mock data. A DCF is only as good as its assumptions — use the sensitivity grid to see how fragile the output is to WACC and terminal growth.
          </p>
        </div>
      </div>
    </div>
  );
}

function DcfInput({ label, unit, v, min, max, step, onChange, hint }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontSize: 12.5, color: "var(--text)", fontWeight: 500 }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 4, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6, padding: "2px 6px" }}>
          <input type="number" value={v} step={step} min={min} max={max}
            onChange={(e) => onChange(Math.max(min, Math.min(max, parseFloat(e.target.value) || 0)))}
            className="mono tnum" style={{ width: 56, border: "none", outline: "none", background: "transparent", color: "var(--text)", fontSize: 13, fontWeight: 600, textAlign: "right" }} />
          <span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>{unit}</span>
        </div>
      </div>
      <input type="range" min={min} max={max} step={step} value={v} onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: "var(--accent)", height: 4 }} />
      {hint && <div style={{ fontSize: 10.5, color: "var(--text-3)", marginTop: 3 }}>{hint}</div>}
    </div>
  );
}

function FcfBars({ flows }) {
  const max = Math.max(...flows.map((f) => f.fcf));
  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 110 }}>
        {flows.map((f) => (
          <div key={f.t} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end", gap: 5 }}>
            <span className="mono tnum" style={{ fontSize: 10, color: "var(--text-3)" }}>{f.pv.toFixed(0)}</span>
            <div style={{ width: "100%", maxWidth: 38, position: "relative", height: (f.fcf / max) * 80, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
              <div style={{ height: (f.pv / f.fcf) * 100 + "%", background: "var(--accent)", borderRadius: "3px 3px 0 0" }} title="Present value" />
              <div style={{ position: "absolute", inset: 0, border: "1px dashed var(--accent)", borderRadius: "3px 3px 0 0", opacity: 0.4 }} title="Undiscounted FCF" />
            </div>
            <span className="mono" style={{ fontSize: 10, color: "var(--text-3)" }}>Y{f.t}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 10, fontSize: 11, color: "var(--text-3)" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 10, height: 10, background: "var(--accent)", borderRadius: 2 }} /> Present value</span>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 10, height: 10, border: "1px dashed var(--accent)", borderRadius: 2 }} /> Undiscounted FCF</span>
      </div>
    </div>
  );
}

/* =================== FINANCIALS =================== */
function buildStatements(c) {
  const rev = c.revenue;
  const shares = c.marketCap / c.price;
  const gm = (c.grossMargin || 40) / 100, om = c.opMargin / 100, nm = c.netMargin / 100;
  return rev.map((r, i) => {
    const grossProfit = r * gm;
    const opInc = r * om;
    const opex = grossProfit - opInc;
    const netInc = r * nm;
    const eps = netInc / shares;
    const equity = r * 0.8 * (0.85 + i * 0.05);
    const debt = equity * c.debtEq;
    const cash = r * 0.28;
    const liab = debt + r * 0.45;
    const assets = equity + liab;
    const opCF = netInc * 1.22;
    const capex = -r * 0.08;
    const fcf = opCF + capex;
    return { year: DATA.YEARS[i], rev, revenue: r, cogs: r - grossProfit, grossProfit, opex, opInc, netInc, eps,
      cash, assets, liab, debt, equity, opCF, capex, fcf };
  });
}

const STATEMENTS = {
  income: { label: "Income statement", rows: [
    { k: "revenue", label: "Revenue", bold: true },
    { k: "cogs", label: "Cost of revenue", neg: true },
    { k: "grossProfit", label: "Gross profit", bold: true },
    { k: "opex", label: "Operating expenses", neg: true },
    { k: "opInc", label: "Operating income", bold: true },
    { k: "netInc", label: "Net income", bold: true, accent: true },
    { k: "eps", label: "Diluted EPS", money: true },
  ]},
  balance: { label: "Balance sheet", rows: [
    { k: "cash", label: "Cash & equivalents" },
    { k: "assets", label: "Total assets", bold: true },
    { k: "debt", label: "Total debt", neg: false },
    { k: "liab", label: "Total liabilities", bold: true },
    { k: "equity", label: "Shareholders' equity", bold: true, accent: true },
  ]},
  cashflow: { label: "Cash flow", rows: [
    { k: "opCF", label: "Operating cash flow", bold: true },
    { k: "capex", label: "Capital expenditure", neg: true },
    { k: "fcf", label: "Free cash flow", bold: true, accent: true },
  ]},
};

function Financials({ ticker, go }) {
  const c = DATA.byTicker[ticker];
  const [tab, setTab] = useState("income");
  const data = useMemo(() => buildStatements(c), [ticker]);
  const def = STATEMENTS[tab];

  const cagr = (k) => {
    const a = data[0][k], b = data[data.length - 1][k];
    if (a <= 0) return null;
    return (Math.pow(b / a, 1 / (data.length - 1)) - 1) * 100;
  };

  return (
    <div className="fade-up" style={{ padding: 24, height: "100%", overflowY: "auto" }}>
      <PageHead title="Financial statements"
        sub={`${c.name} · 6-year history ($B unless noted) · mock data`}
        right={<CompanyPicker ticker={ticker} onPick={(t) => go("financials", t)} />} />

      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {Object.entries(STATEMENTS).map(([k, v]) => (
          <button key={k} onClick={() => setTab(k)} style={{
            padding: "8px 16px", borderRadius: "var(--r-md)", fontSize: 13, fontWeight: 600,
            background: tab === k ? "var(--surface)" : "transparent",
            color: tab === k ? "var(--text)" : "var(--text-3)",
            border: "1px solid " + (tab === k ? "var(--border)" : "transparent"),
            boxShadow: tab === k ? "var(--shadow)" : "none" }}>{v.label}</button>
        ))}
      </div>

      <Card pad={0}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "12px 16px", fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-3)", position: "sticky", left: 0, background: "var(--surface)", borderBottom: "1px solid var(--border)", minWidth: 200 }}>Line item</th>
                {data.map((d) => (
                  <th key={d.year} className="mono" style={{ textAlign: "right", padding: "12px 16px", fontSize: 12, fontWeight: 600, color: d.year === DATA.YEARS[DATA.YEARS.length - 1] ? "var(--text)" : "var(--text-2)", borderBottom: "1px solid var(--border)" }}>{d.year}</th>
                ))}
                <th style={{ textAlign: "right", padding: "12px 16px", fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-3)", borderBottom: "1px solid var(--border)" }}>Trend</th>
                <th style={{ textAlign: "right", padding: "12px 16px", fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-3)", borderBottom: "1px solid var(--border)" }}>5Y CAGR</th>
              </tr>
            </thead>
            <tbody>
              {def.rows.map((row) => {
                const series = data.map((d) => d[row.k]);
                const cg = cagr(row.k);
                return (
                  <tr key={row.k} style={{ borderBottom: "1px solid var(--border)", background: row.accent ? "var(--accent-bg)" : "transparent" }}>
                    <td style={{ padding: "11px 16px", position: "sticky", left: 0, background: row.accent ? "var(--surface)" : "var(--surface)",
                      fontWeight: row.bold ? 600 : 400, color: row.bold ? "var(--text)" : "var(--text-2)", fontSize: 12.5 }}>{row.label}</td>
                    {data.map((d) => {
                      const v = d[row.k];
                      const txt = row.money ? "$" + v.toFixed(2) : (row.neg ? "(" + Math.abs(v).toFixed(1) + ")" : v.toFixed(1));
                      return <td key={d.year} className="mono tnum" style={{ textAlign: "right", padding: "11px 16px", fontWeight: row.bold ? 600 : 400,
                        color: row.neg ? "var(--text-3)" : "var(--text)" }}>{txt}</td>;
                    })}
                    <td style={{ padding: "8px 16px", textAlign: "right" }}><div style={{ display: "inline-block" }}><Sparkline data={series} w={72} h={22} color="var(--accent)" /></div></td>
                    <td className="mono tnum" style={{ textAlign: "right", padding: "11px 16px" }}>
                      {cg == null ? <span style={{ color: "var(--text-3)" }}>—</span> : <span style={{ color: cg >= 0 ? "var(--up)" : "var(--down)", fontWeight: 600 }}>{fmt.pct(cg, 1)}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* margin / ratio strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginTop: 16 }}>
        {tab === "income" && [
          ["Gross margin", c.grossMargin ? fmt.pctPlain(c.grossMargin) : "—"],
          ["Operating margin", fmt.pctPlain(c.opMargin)],
          ["Net margin", fmt.pctPlain(c.netMargin)],
          ["Revenue CAGR", fmt.pct(cagr("revenue"), 1)],
        ].map(([l, v]) => <MiniStat key={l} label={l} value={v} />)}
        {tab === "balance" && [
          ["Debt / equity", fmt.num(c.debtEq, 2)],
          ["Current ratio", c.currentRatio ? fmt.num(c.currentRatio, 2) : "—"],
          ["ROE", fmt.pctPlain(c.roe)],
          ["Equity CAGR", fmt.pct(cagr("equity"), 1)],
        ].map(([l, v]) => <MiniStat key={l} label={l} value={v} />)}
        {tab === "cashflow" && [
          ["FCF margin", fmt.pctPlain(data[data.length - 1].fcf / data[data.length - 1].revenue * 100)],
          ["FCF yield", c.fcfYield ? fmt.pctPlain(c.fcfYield) : "—"],
          ["Capex / rev", fmt.pctPlain(Math.abs(data[data.length - 1].capex) / data[data.length - 1].revenue * 100)],
          ["FCF CAGR", fmt.pct(cagr("fcf"), 1)],
        ].map(([l, v]) => <MiniStat key={l} label={l} value={v} />)}
      </div>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "12px 14px" }}>
      <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>{label}</div>
      <div className="mono tnum" style={{ fontSize: 18, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

export { Valuation, Financials, CompanyPicker, DcfInput, FcfBars, MiniStat, buildStatements };
