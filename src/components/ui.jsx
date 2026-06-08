/* ============================================================
   ui.jsx — shared primitives: formatters, icons, charts, scores
   ============================================================ */
import { useState, useRef, useEffect, useId } from "react";
import { useTranslation } from "react-i18next";
import { fmt, scoreColor, scoreLabel } from "../format.js";

/* ---------------- icons (simple stroke) ---------------- */
const ICONS = {
  watchlist: "M3 5h14M3 10h14M3 15h9",
  company: "M4 17V4h8v13M12 8h4v9M4 17h14M7 7h2M7 10h2M7 13h2",
  screener: "M3 5h14M6 10h8M9 15h2",
  compare: "M4 4h5v13H4zM11 4h5v13h-5z",
  valuation: "M10 3v14M10 3l5 4M10 3L5 7M4 17h12",
  financials: "M5 3h7l4 4v10H5zM12 3v4h4M8 11h5M8 14h5",
  search: "M9 3a6 6 0 104.5 10.03L17 16.5",
  sun: "M10 3v2M10 15v2M3 10h2M15 10h2M5.2 5.2l1.4 1.4M13.4 13.4l1.4 1.4M14.8 5.2l-1.4 1.4M6.6 13.4l-1.4 1.4",
  moon: "M16 11.5A6 6 0 018.5 4 6 6 0 1016 11.5z",
  plus: "M10 4v12M4 10h12",
  check: "M4 10l4 4 8-9",
  star: "M10 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L2.2 7.7l5.4-.8z",
  arrowUp: "M10 16V4M10 4l5 5M10 4L5 9",
  arrowDown: "M10 4v12M10 16l5-5M10 16l-5-5",
  chevR: "M7 4l6 6-6 6",
  chevD: "M4 7l6 6 6-6",
  x: "M5 5l10 10M15 5L5 15",
  bolt: "M11 2L4 11h5l-1 7 7-9h-5z",
  download: "M10 3v9M10 12l4-4M10 12L6 8M4 16h12",
  globe: "M10 3a7 7 0 100 14 7 7 0 000-14M3 10h14M10 3c2.6 2 2.6 12 0 14M10 3c-2.6 2-2.6 12 0 14",
};
function Icon({ name, size = 18, stroke = 1.6, fill = false, style }) {
  const d = ICONS[name] || "";
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none"
      style={{ display: "block", flex: "none", ...style }}>
      <path d={d} stroke="currentColor" strokeWidth={stroke}
        strokeLinecap="round" strokeLinejoin="round"
        fill={fill ? "currentColor" : "none"} />
    </svg>
  );
}

/* ---------------- ticker monogram tile ---------------- */
function Mono({ ticker, size = 34 }) {
  // deterministic hue from ticker
  let h = 0; for (const ch of ticker) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return (
    <div className="mono" style={{
      width: size, height: size, borderRadius: 7, flex: "none",
      display: "grid", placeItems: "center",
      fontSize: size * 0.32, fontWeight: 600, letterSpacing: "-0.02em",
      color: `oklch(0.96 0.02 ${h})`,
      background: `oklch(0.5 0.13 ${h})`,
      boxShadow: "inset 0 1px 0 rgba(255,255,255,.12)",
    }}>{ticker.slice(0, 2)}</div>
  );
}

/* ---------------- Delta (colored change) ---------------- */
function Delta({ value, pct, suffix = "%", arrow = true, size }) {
  if (value == null) return <span className="mono" style={{ color: "var(--text-3)" }}>—</span>;
  const up = value >= 0;
  return (
    <span className="mono tnum" style={{
      color: up ? "var(--up)" : "var(--down)", fontWeight: 500,
      display: "inline-flex", alignItems: "center", gap: 3, fontSize: size,
    }}>
      {arrow && <Icon name={up ? "arrowUp" : "arrowDown"} size={(size || 13) * 0.92} stroke={2.2} />}
      {(up ? "+" : "") + value.toFixed(2)}{pct ? suffix : ""}
    </span>
  );
}

/* ---------------- Sparkline ---------------- */
function Sparkline({ data, w = 88, h = 28, color, strokeW = 1.5, fillArea = false }) {
  const id = "sp" + useId().replace(/:/g, "");  // hook antes de cualquier return (rules-of-hooks)
  if (!data || data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - ((v - min) / rng) * (h - 2) - 1,
  ]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const up = data[data.length - 1] >= data[0];
  const c = color || (up ? "var(--up)" : "var(--down)");
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      {fillArea && (
        <>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c} stopOpacity="0.22" />
              <stop offset="100%" stopColor={c} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={`${line} L ${w} ${h} L 0 ${h} Z`} fill={`url(#${id})`} />
        </>
      )}
      <path d={line} fill="none" stroke={c} strokeWidth={strokeW} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ---------------- AreaChart (interactive crosshair) ---------------- */
function AreaChart({ data, h = 260, color, baseline }) {
  const wrapRef = useRef(null);
  const [W, setW] = useState(640);
  const [hover, setHover] = useState(null);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);
  const padY = 14;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const X = (i) => (i / (data.length - 1)) * W;
  const Y = (v) => h - padY - ((v - min) / rng) * (h - padY * 2);
  const pts = data.map((v, i) => [X(i), Y(v)]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const up = data[data.length - 1] >= data[0];
  const c = color || (up ? "var(--up)" : "var(--down)");
  const id = "ac" + useId().replace(/:/g, "");
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const i = Math.max(0, Math.min(data.length - 1, Math.round((x / W) * (data.length - 1))));
    setHover(i);
  };
  return (
    <div ref={wrapRef} style={{ position: "relative", width: "100%" }}>
      <svg width="100%" height={h} viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none"
        onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={c} stopOpacity="0.20" />
            <stop offset="100%" stopColor={c} stopOpacity="0" />
          </linearGradient>
        </defs>
        {baseline != null && (
          <line x1="0" x2={W} y1={Y(baseline)} y2={Y(baseline)}
            stroke="var(--border-strong)" strokeWidth="1" strokeDasharray="3 4" />
        )}
        <path d={`${line} L ${W} ${h} L 0 ${h} Z`} fill={`url(#${id})`} />
        <path d={line} fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        {hover != null && (
          <g>
            <line x1={pts[hover][0]} x2={pts[hover][0]} y1={0} y2={h} stroke="var(--border-strong)" strokeWidth="1" />
            <circle cx={pts[hover][0]} cy={pts[hover][1]} r="3.5" fill={c} stroke="var(--surface)" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hover != null && (
        <div className="mono tnum" style={{
          position: "absolute", top: 4,
          left: Math.min(Math.max(pts[hover][0] - 30, 0), W - 64),
          background: "var(--surface-2)", border: "1px solid var(--border)",
          borderRadius: 5, padding: "2px 7px", fontSize: 11, color: "var(--text)",
          pointerEvents: "none", boxShadow: "var(--shadow)", whiteSpace: "nowrap",
        }}>{fmt.price(data[hover])}</div>
      )}
    </div>
  );
}

/* ---------------- ScoreRing (composite) ---------------- */
function ScoreRing({ score, size = 76, stroke = 7, showLabel = true }) {
  const { t } = useTranslation();
  if (score == null) return (
    <div className="mono" style={{
      width: size, height: size, flex: "none", display: "grid", placeItems: "center",
      borderRadius: "50%", border: `${stroke}px solid var(--border)`,
      color: "var(--text-3)", fontSize: size * 0.3, fontWeight: 600,
    }}>—</div>
  );
  const s = Math.max(0, Math.min(100, score)); // clamp (L22): un score fuera de rango no desborda el arco
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const c = scoreColor(score);
  return (
    <div style={{ position: "relative", width: size, height: size, flex: "none" }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={c} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={circ}
          strokeDashoffset={circ * (1 - s / 100)}
          style={{ transition: "stroke-dashoffset .6s cubic-bezier(.2,.7,.3,1)" }} />
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "grid", placeItems: "center",
        textAlign: "center", lineHeight: 1,
      }}>
        <div>
          <div className="mono tnum" style={{ fontSize: size * 0.3, fontWeight: 600, color: "var(--text)" }}>{score}</div>
          {showLabel && <div style={{ fontSize: size * 0.12, color: c, fontWeight: 600, marginTop: 2 }}>{t("score." + scoreLabel(score))}</div>}
        </div>
      </div>
    </div>
  );
}

/* ---------------- ScoreBar (sub-score) ---------------- */
function ScoreBar({ label, score, sub }) {
  const c = score == null ? "var(--border)" : scoreColor(score);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ width: 64, flex: "none" }}>
        <div style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 500 }}>{label}</div>
        {sub && <div style={{ fontSize: 10, color: "var(--text-3)" }}>{sub}</div>}
      </div>
      <div style={{ flex: 1, height: 6, borderRadius: 4, background: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: Math.max(0, Math.min(100, score ?? 0)) + "%", height: "100%", background: c, borderRadius: 4, transition: "width .5s ease" }} />
      </div>
      <div className="mono tnum" style={{ width: 24, textAlign: "right", fontSize: 12, fontWeight: 600, color: "var(--text)" }}>{score ?? "—"}</div>
    </div>
  );
}

/* ---------------- Pill ---------------- */
function Pill({ children, tone = "neutral", onClick, active, style }) {
  const tones = {
    neutral: { bg: "var(--surface-2)", fg: "var(--text-2)", bd: "var(--border)" },
    accent: { bg: "var(--accent-bg)", fg: "var(--accent)", bd: "transparent" },
    up: { bg: "var(--up-bg)", fg: "var(--up)", bd: "transparent" },
    down: { bg: "var(--down-bg)", fg: "var(--down)", bd: "transparent" },
  };
  const t = tones[tone];
  return (
    <span onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 500,
      background: active ? "var(--accent)" : t.bg,
      color: active ? "white" : t.fg,
      border: "1px solid " + (active ? "transparent" : t.bd),
      cursor: onClick ? "pointer" : "default", whiteSpace: "nowrap", ...style,
    }}>{children}</span>
  );
}

/* ---------------- Card ---------------- */
function Card({ title, action, children, pad = 16, style }) {
  return (
    <section style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: "var(--r-lg)", overflow: "hidden", ...style,
    }}>
      {title && (
        <header style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "11px 16px", borderBottom: "1px solid var(--border)",
        }}>
          <h3 style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-2)" }}>{title}</h3>
          {action}
        </header>
      )}
      <div style={{ padding: pad }}>{children}</div>
    </section>
  );
}

/* ---------------- Stat (metric cell) ---------------- */
function Stat({ label, value, sub, tone }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 3, whiteSpace: "nowrap" }}>{label}</div>
      <div className="mono tnum" style={{ fontSize: 16, fontWeight: 600, color: tone || "var(--text)", whiteSpace: "nowrap" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

export {
  Icon, Mono, Delta, Sparkline, AreaChart,
  ScoreRing, ScoreBar, Pill, Card, Stat,
};
