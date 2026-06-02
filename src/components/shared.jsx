/* ============================================================
   shared.jsx — presentational primitives reused across screens
   (table cells, score widgets, page header)
   ============================================================ */
import { scoreColor } from "./ui.jsx";

/* ---------- table: sortable column header ---------- */
function Th({ children, k, sort, setSort, align = "right", w }) {
  const active = sort && sort.k === k;
  return (
    <th
      onClick={k ? () => setSort({ k, dir: active && sort.dir === "desc" ? "asc" : "desc" }) : undefined}
      style={{
        textAlign: align, padding: "8px 12px", fontSize: 10.5, fontWeight: 600,
        letterSpacing: "0.05em", textTransform: "uppercase", color: active ? "var(--text)" : "var(--text-3)",
        cursor: k ? "pointer" : "default", whiteSpace: "nowrap", userSelect: "none",
        position: "sticky", top: 0, background: "var(--surface)", zIndex: 1, width: w,
        borderBottom: "1px solid var(--border)",
      }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 3, flexDirection: align === "right" ? "row-reverse" : "row" }}>
        {children}
        {active && <span className="mono" style={{ fontSize: 9, color: "var(--accent)" }}>{sort.dir === "desc" ? "▼" : "▲"}</span>}
      </span>
    </th>
  );
}
function Td({ children, align = "right", style }) {
  return <td style={{ textAlign: align, padding: "0 12px", whiteSpace: "nowrap", ...style }}>{children}</td>;
}

/* ---------- compact score chip ---------- */
function ScorePip({ score }) {
  return (
    <span className="mono tnum" style={{
      display: "inline-grid", placeItems: "center", width: 30, height: 22, borderRadius: 5,
      fontSize: 12, fontWeight: 600, color: scoreColor(score),
      background: scoreColor(score).replace("0.70", "0.70").replace(")", " / 0.13)").replace("oklch(", "oklch("),
    }}>{score}</span>
  );
}

/* ---------- composite score mini-bar ---------- */
function CompositeMini({ score }) {
  const c = scoreColor(score);
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
      <div style={{ width: 40, height: 6, borderRadius: 3, background: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: score + "%", height: "100%", background: c }} />
      </div>
      <span className="mono tnum" style={{ fontSize: 13, fontWeight: 600, color: c, width: 18, textAlign: "right" }}>{score}</span>
    </div>
  );
}

/* ---------- page header ---------- */
function PageHead({ title, sub, right }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 18 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>{title}</h1>
        {sub && <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 2 }}>{sub}</div>}
      </div>
      {right}
    </div>
  );
}

export { Th, Td, ScorePip, CompositeMini, PageHead };
