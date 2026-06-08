/* ============================================================
   format.js — formatters + score helpers (puros, sin JSX).
   Viven fuera de ui.jsx para que ese fichero solo exporte
   componentes (react-refresh/only-export-components).
   ============================================================ */

/* ---------------- formatters ---------------- */
const fmt = {
  price: (n) => n == null ? "—" : "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  num: (n, d = 2) => n == null ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }),
  // n in billions
  cap: (n) => {
    if (n == null) return "—";
    if (n >= 1000) return "$" + (n / 1000).toFixed(2) + "T";
    return "$" + n.toFixed(n >= 100 ? 0 : 1) + "B";
  },
  mult: (n) => n == null ? "—" : n.toFixed(1) + "×",
  pct: (n, d = 2) => n == null ? "—" : (n > 0 ? "+" : "") + n.toFixed(d) + "%",
  pctPlain: (n, d = 1) => n == null ? "—" : n.toFixed(d) + "%",
  signed: (n, d = 2) => n == null ? "—" : (n > 0 ? "+" : "") + n.toFixed(d),
};

/* ---------------- score color ramp ---------------- */
function scoreColor(s) {
  const hue = 25 + 1.3 * Math.max(0, Math.min(100, s)); // 25(red) → 155(green)
  return `oklch(0.70 0.155 ${hue})`;
}
// Devuelve una CLAVE i18n estable ("score.*"); el texto visible lo resuelve t().
function scoreLabel(s) {
  if (s >= 80) return "strong";
  if (s >= 65) return "good";
  if (s >= 45) return "fair";
  if (s >= 30) return "weak";
  return "poor";
}

export { fmt, scoreColor, scoreLabel };
