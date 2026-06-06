/* ============================================================
   api.js — cliente HTTP del backend + hook useAsync
   Reemplaza el mock de data.js: las pantallas piden datos reales.
   Base configurable con VITE_API_URL (por defecto localhost:8000).
   ============================================================ */
import { useState, useEffect } from "react";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path, params) {
  const url = new URL(BASE + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  // Watchlist / Compare: por tickers; sin tickers → lista paginada
  companies: (tickers) =>
    get("/companies", tickers && tickers.length ? { tickers: tickers.join(",") } : { limit: 50 }),
  company: (ticker) => get(`/companies/${encodeURIComponent(ticker)}`),
  prices: (ticker, range = "1Y") => get(`/companies/${encodeURIComponent(ticker)}/prices`, { range }),
  financials: (ticker) => get(`/companies/${encodeURIComponent(ticker)}/financials`),
  screen: (params) => get("/screener", params),
  search: (q, limit = 8) => get("/search", { q, limit }),
  indices: () => get("/market/indices"),
  marketStatus: () => get("/market/status"),
};

/* useAsync — ejecuta `fn` y expone {loading, error, data}; re-ejecuta al cambiar deps. */
export function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  useEffect(() => {
    let alive = true;
    setState({ loading: true, error: null, data: null });
    Promise.resolve()
      .then(fn)
      .then(
        (data) => { if (alive) setState({ loading: false, error: null, data }); },
        (error) => { if (alive) setState({ loading: false, error, data: null }); },
      );
    return () => { alive = false; };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}
