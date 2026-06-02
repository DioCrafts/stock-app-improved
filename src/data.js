/* ============================================================
   data.js — Mock dataset for the equity research terminal
   Attaches window.DATA with companies, history generators, etc.
   All figures are fictional / illustrative.
   ============================================================ */
export const DATA = (function () {
  // ---- tiny seeded RNG so sparklines look natural & stable ----
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Build a price series that trends toward `now` with some noise.
  function priceSeries(seed, n, start, end, vol) {
    const rnd = mulberry32(seed);
    const out = [];
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1);
      const trend = start + (end - start) * t;
      const noise = (rnd() - 0.5) * vol * trend;
      out.push(Math.max(0.01, trend + noise));
    }
    out[out.length - 1] = end;
    return out;
  }

  // Build a yearly series for financial line-items.
  function yearSeries(seed, n, start, cagr, vol) {
    const rnd = mulberry32(seed);
    const out = [];
    let v = start;
    for (let i = 0; i < n; i++) {
      out.push(v);
      v = v * (1 + cagr + (rnd() - 0.5) * vol);
    }
    return out;
  }

  const YEARS = [2020, 2021, 2022, 2023, 2024, 2025];

  // helper to assemble a company record
  function C(o) {
    // composite weighted score: value 35, growth 30, health 20, momentum 15
    const composite = Math.round(
      o.scores.value * 0.35 +
      o.scores.growth * 0.30 +
      o.scores.health * 0.20 +
      o.scores.momentum * 0.15
    );
    return Object.assign({ scores: Object.assign({ composite }, o.scores) }, o, {
      scores: Object.assign({}, o.scores, { composite }),
    });
  }

  const companies = [
    C({
      ticker: "NVDA", name: "NVIDIA Corp", sector: "Semiconductors", exchange: "NASDAQ",
      price: 131.26, change: 2.84, prevClose: 127.63, marketCap: 3231, currency: "USD",
      pe: 54.2, fwdPe: 33.8, peg: 1.1, pb: 48.1, ps: 33.4, evEbitda: 49.2,
      divYield: 0.02, roe: 91.2, roic: 78.4, grossMargin: 75.0, opMargin: 62.1, netMargin: 55.8,
      revGrowth: 114.2, epsGrowth: 147.0, fcfYield: 1.6, debtEq: 0.17, currentRatio: 4.1,
      beta: 1.66, employees: 29600,
      scores: { value: 38, growth: 99, health: 92, momentum: 95 },
      hist: priceSeries(11, 60, 49, 131.26, 0.05),
      revenue: yearSeries(101, 6, 16.7, 0.45, 0.12),
      desc: "Designs GPUs and accelerated-computing platforms powering AI, data centers, gaming and robotics.",
    }),
    C({
      ticker: "AAPL", name: "Apple Inc", sector: "Consumer Electronics", exchange: "NASDAQ",
      price: 196.89, change: -0.62, prevClose: 198.12, marketCap: 2980, currency: "USD",
      pe: 30.6, fwdPe: 27.4, peg: 2.9, pb: 47.3, ps: 7.6, evEbitda: 22.1,
      divYield: 0.51, roe: 147.0, roic: 56.2, grossMargin: 46.2, opMargin: 31.5, netMargin: 24.3,
      revGrowth: 2.0, epsGrowth: 7.1, fcfYield: 3.4, debtEq: 1.45, currentRatio: 0.92,
      beta: 1.24, employees: 164000,
      scores: { value: 52, growth: 48, health: 78, momentum: 60 },
      hist: priceSeries(12, 60, 170, 196.89, 0.04),
      revenue: yearSeries(102, 6, 274, 0.06, 0.05),
      desc: "Designs and sells iPhone, Mac, iPad, wearables and a fast-growing high-margin Services segment.",
    }),
    C({
      ticker: "MSFT", name: "Microsoft Corp", sector: "Software — Infrastructure", exchange: "NASDAQ",
      price: 467.56, change: 1.12, prevClose: 462.38, marketCap: 3476, currency: "USD",
      pe: 38.4, fwdPe: 31.2, peg: 2.1, pb: 12.8, ps: 13.6, evEbitda: 26.0,
      divYield: 0.71, roe: 35.1, roic: 28.7, grossMargin: 69.4, opMargin: 44.6, netMargin: 35.9,
      revGrowth: 15.7, epsGrowth: 21.8, fcfYield: 2.3, debtEq: 0.33, currentRatio: 1.27,
      beta: 0.91, employees: 228000,
      scores: { value: 49, growth: 78, health: 90, momentum: 74 },
      hist: priceSeries(13, 60, 410, 467.56, 0.035),
      revenue: yearSeries(103, 6, 143, 0.14, 0.04),
      desc: "Cloud (Azure), productivity (Microsoft 365), Windows and an expanding AI Copilot franchise.",
    }),
    C({
      ticker: "GOOGL", name: "Alphabet Inc", sector: "Interactive Media", exchange: "NASDAQ",
      price: 175.43, change: 0.88, prevClose: 173.90, marketCap: 2140, currency: "USD",
      pe: 24.1, fwdPe: 20.6, peg: 1.3, pb: 6.9, ps: 6.4, evEbitda: 17.3,
      divYield: 0.46, roe: 30.8, roic: 26.1, grossMargin: 58.0, opMargin: 32.5, netMargin: 27.7,
      revGrowth: 13.9, epsGrowth: 31.2, fcfYield: 3.1, debtEq: 0.10, currentRatio: 2.1,
      beta: 1.03, employees: 182500,
      scores: { value: 68, growth: 74, health: 94, momentum: 70 },
      hist: priceSeries(14, 60, 150, 175.43, 0.04),
      revenue: yearSeries(104, 6, 182, 0.16, 0.04),
      desc: "Google Search, YouTube, Android, Google Cloud and the Other Bets venture portfolio.",
    }),
    C({
      ticker: "AMZN", name: "Amazon.com Inc", sector: "Internet Retail", exchange: "NASDAQ",
      price: 207.05, change: 1.45, prevClose: 204.10, marketCap: 2170, currency: "USD",
      pe: 41.5, fwdPe: 32.0, peg: 1.0, pb: 7.7, ps: 3.4, evEbitda: 18.9,
      divYield: 0, roe: 20.5, roic: 13.8, grossMargin: 48.9, opMargin: 10.8, netMargin: 8.0,
      revGrowth: 12.5, epsGrowth: 88.0, fcfYield: 1.9, debtEq: 0.49, currentRatio: 1.06,
      beta: 1.15, employees: 1556000,
      scores: { value: 47, growth: 82, health: 80, momentum: 76 },
      hist: priceSeries(15, 60, 178, 207.05, 0.045),
      revenue: yearSeries(105, 6, 386, 0.13, 0.03),
      desc: "E-commerce marketplace, AWS cloud infrastructure, advertising and logistics.",
    }),
    C({
      ticker: "META", name: "Meta Platforms", sector: "Interactive Media", exchange: "NASDAQ",
      price: 593.12, change: 2.01, prevClose: 581.40, marketCap: 1500, currency: "USD",
      pe: 27.6, fwdPe: 23.1, peg: 0.9, pb: 8.4, ps: 9.5, evEbitda: 17.0,
      divYield: 0.34, roe: 33.4, roic: 27.9, grossMargin: 81.5, opMargin: 42.0, netMargin: 34.6,
      revGrowth: 22.1, epsGrowth: 60.5, fcfYield: 3.0, debtEq: 0.30, currentRatio: 2.7,
      beta: 1.21, employees: 70800,
      scores: { value: 64, growth: 86, health: 91, momentum: 82 },
      hist: priceSeries(16, 60, 480, 593.12, 0.05),
      revenue: yearSeries(106, 6, 86, 0.18, 0.06),
      desc: "Facebook, Instagram, WhatsApp and Reality Labs; advertising drives the vast majority of revenue.",
    }),
    C({
      ticker: "TSLA", name: "Tesla Inc", sector: "Auto Manufacturers", exchange: "NASDAQ",
      price: 342.69, change: -3.10, prevClose: 353.66, marketCap: 1100, currency: "USD",
      pe: 112.4, fwdPe: 88.0, peg: 4.8, pb: 13.9, ps: 11.2, evEbitda: 70.5,
      divYield: 0, roe: 12.4, roic: 9.8, grossMargin: 17.7, opMargin: 8.2, netMargin: 7.3,
      revGrowth: 1.0, epsGrowth: -23.0, fcfYield: 0.8, debtEq: 0.08, currentRatio: 2.0,
      beta: 2.31, employees: 125700,
      scores: { value: 14, growth: 40, health: 84, momentum: 38 },
      hist: priceSeries(17, 60, 250, 342.69, 0.08),
      revenue: yearSeries(107, 6, 31.5, 0.30, 0.10),
      desc: "Electric vehicles, energy storage/solar, and autonomy & robotics ambitions.",
    }),
    C({
      ticker: "AMD", name: "Advanced Micro Devices", sector: "Semiconductors", exchange: "NASDAQ",
      price: 122.41, change: 1.95, prevClose: 120.07, marketCap: 198, currency: "USD",
      pe: 98.2, fwdPe: 28.4, peg: 1.4, pb: 3.1, ps: 8.1, evEbitda: 41.0,
      divYield: 0, roe: 3.4, roic: 3.0, grossMargin: 49.4, opMargin: 6.1, netMargin: 7.0,
      revGrowth: 13.7, epsGrowth: 25.0, fcfYield: 1.5, debtEq: 0.06, currentRatio: 2.6,
      beta: 1.69, employees: 26000,
      scores: { value: 32, growth: 72, health: 86, momentum: 66 },
      hist: priceSeries(18, 60, 138, 122.41, 0.07),
      revenue: yearSeries(108, 6, 9.8, 0.22, 0.08),
      desc: "CPUs, GPUs and adaptive computing (Xilinx) competing in data-center and client markets.",
    }),
    C({
      ticker: "JPM", name: "JPMorgan Chase", sector: "Banks — Diversified", exchange: "NYSE",
      price: 248.91, change: 0.54, prevClose: 247.57, marketCap: 700, currency: "USD",
      pe: 12.6, fwdPe: 14.1, peg: 1.8, pb: 2.1, ps: 3.6, evEbitda: null,
      divYield: 2.0, roe: 17.0, roic: null, grossMargin: null, opMargin: 41.0, netMargin: 33.0,
      revGrowth: 11.0, epsGrowth: 9.0, fcfYield: null, debtEq: 1.3, currentRatio: null,
      beta: 1.09, employees: 311000,
      scores: { value: 80, growth: 52, health: 72, momentum: 64 },
      hist: priceSeries(19, 60, 210, 248.91, 0.03),
      revenue: yearSeries(109, 6, 119, 0.07, 0.04),
      desc: "Largest US bank: consumer & community banking, corporate & investment bank, asset management.",
    }),
    C({
      ticker: "V", name: "Visa Inc", sector: "Credit Services", exchange: "NYSE",
      price: 348.17, change: 0.21, prevClose: 347.44, marketCap: 690, currency: "USD",
      pe: 31.0, fwdPe: 27.2, peg: 2.3, pb: 14.6, ps: 17.3, evEbitda: 24.4,
      divYield: 0.74, roe: 48.2, roic: 38.0, grossMargin: 80.0, opMargin: 66.5, netMargin: 54.3,
      revGrowth: 10.0, epsGrowth: 14.0, fcfYield: 3.2, debtEq: 0.50, currentRatio: 1.3,
      beta: 0.95, employees: 31600,
      scores: { value: 55, growth: 66, health: 95, momentum: 68 },
      hist: priceSeries(20, 60, 300, 348.17, 0.03),
      revenue: yearSeries(110, 6, 21.8, 0.11, 0.03),
      desc: "Global payments network earning fees on transaction volume across credit, debit and B2B rails.",
    }),
    C({
      ticker: "UNH", name: "UnitedHealth Group", sector: "Healthcare Plans", exchange: "NYSE",
      price: 312.45, change: -1.80, prevClose: 318.18, marketCap: 287, currency: "USD",
      pe: 13.9, fwdPe: 12.0, peg: 1.2, pb: 3.4, ps: 0.7, evEbitda: 9.1,
      divYield: 2.8, roe: 24.0, roic: 14.0, grossMargin: 22.0, opMargin: 8.0, netMargin: 5.5,
      revGrowth: 8.0, epsGrowth: 11.0, fcfYield: 6.5, debtEq: 0.72, currentRatio: 0.8,
      beta: 0.55, employees: 440000,
      scores: { value: 76, growth: 58, health: 70, momentum: 35 },
      hist: priceSeries(21, 60, 520, 312.45, 0.06),
      revenue: yearSeries(111, 6, 257, 0.10, 0.02),
      desc: "Health insurance (UnitedHealthcare) plus Optum health-services and pharmacy-benefits engine.",
    }),
    C({
      ticker: "COST", name: "Costco Wholesale", sector: "Discount Stores", exchange: "NASDAQ",
      price: 978.34, change: 0.67, prevClose: 971.83, marketCap: 434, currency: "USD",
      pe: 54.0, fwdPe: 48.0, peg: 4.2, pb: 17.8, ps: 1.7, evEbitda: 33.0,
      divYield: 0.5, roe: 31.0, roic: 22.0, grossMargin: 12.6, opMargin: 3.7, netMargin: 2.9,
      revGrowth: 6.5, epsGrowth: 12.0, fcfYield: 1.8, debtEq: 0.30, currentRatio: 1.0,
      beta: 0.79, employees: 333000,
      scores: { value: 28, growth: 60, health: 88, momentum: 72 },
      hist: priceSeries(22, 60, 880, 978.34, 0.03),
      revenue: yearSeries(112, 6, 166, 0.09, 0.02),
      desc: "Membership-warehouse retailer with durable renewal rates and thin but reliable retail margins.",
    }),
    C({
      ticker: "KO", name: "Coca-Cola Co", sector: "Beverages", exchange: "NYSE",
      price: 71.28, change: 0.12, prevClose: 71.19, marketCap: 307, currency: "USD",
      pe: 26.3, fwdPe: 23.0, peg: 3.5, pb: 11.2, ps: 6.5, evEbitda: 19.5,
      divYield: 2.9, roe: 42.0, roic: 17.0, grossMargin: 60.5, opMargin: 29.0, netMargin: 23.0,
      revGrowth: 3.0, epsGrowth: 6.5, fcfYield: 3.0, debtEq: 1.6, currentRatio: 1.1,
      beta: 0.58, employees: 79100,
      scores: { value: 50, growth: 36, health: 66, momentum: 55 },
      hist: priceSeries(23, 60, 62, 71.28, 0.025),
      revenue: yearSeries(113, 6, 33, 0.05, 0.02),
      desc: "World's largest beverage company; concentrate-led model with high margins and a dividend record.",
    }),
    C({
      ticker: "XOM", name: "Exxon Mobil", sector: "Oil & Gas Integrated", exchange: "NYSE",
      price: 113.66, change: -0.95, prevClose: 114.75, marketCap: 502, currency: "USD",
      pe: 14.2, fwdPe: 13.0, peg: 2.8, pb: 1.9, ps: 1.4, evEbitda: 6.6,
      divYield: 3.5, roe: 14.0, roic: 11.0, grossMargin: 31.0, opMargin: 13.0, netMargin: 9.8,
      revGrowth: -2.0, epsGrowth: -18.0, fcfYield: 5.8, debtEq: 0.20, currentRatio: 1.35,
      beta: 0.85, employees: 61500,
      scores: { value: 78, growth: 24, health: 82, momentum: 48 },
      hist: priceSeries(24, 60, 118, 113.66, 0.04),
      revenue: yearSeries(114, 6, 285, 0.02, 0.10),
      desc: "Integrated oil & gas: upstream production, refining and chemicals, with Permian & Guyana growth.",
    }),
    C({
      ticker: "CRM", name: "Salesforce Inc", sector: "Software — Application", exchange: "NYSE",
      price: 267.84, change: 1.33, prevClose: 264.32, marketCap: 257, currency: "USD",
      pe: 42.0, fwdPe: 26.0, peg: 1.6, pb: 4.4, ps: 6.9, evEbitda: 24.0,
      divYield: 0.6, roe: 10.5, roic: 8.0, grossMargin: 76.4, opMargin: 19.0, netMargin: 16.0,
      revGrowth: 9.0, epsGrowth: 24.0, fcfYield: 4.2, debtEq: 0.18, currentRatio: 1.05,
      beta: 1.30, employees: 72000,
      scores: { value: 44, growth: 64, health: 84, momentum: 58 },
      hist: priceSeries(25, 60, 300, 267.84, 0.05),
      revenue: yearSeries(115, 6, 21.3, 0.17, 0.03),
      desc: "Cloud CRM leader spanning Sales, Service, Marketing, Data Cloud and the Agentforce AI layer.",
    }),
    C({
      ticker: "NFLX", name: "Netflix Inc", sector: "Entertainment", exchange: "NASDAQ",
      price: 891.22, change: 2.44, prevClose: 869.99, marketCap: 383, currency: "USD",
      pe: 49.0, fwdPe: 38.0, peg: 1.7, pb: 18.0, ps: 11.5, evEbitda: 38.0,
      divYield: 0, roe: 37.0, roic: 23.0, grossMargin: 46.0, opMargin: 27.0, netMargin: 22.0,
      revGrowth: 15.0, epsGrowth: 50.0, fcfYield: 1.9, debtEq: 0.66, currentRatio: 1.2,
      beta: 1.28, employees: 14000,
      scores: { value: 36, growth: 80, health: 80, momentum: 84 },
      hist: priceSeries(26, 60, 690, 891.22, 0.055),
      revenue: yearSeries(116, 6, 25, 0.13, 0.03),
      desc: "Global streaming with a maturing ad tier, password-sharing crackdown and improving free cash flow.",
    }),
  ];

  const byTicker = {};
  companies.forEach((c) => (byTicker[c.ticker] = c));

  // default watchlist
  const watchlist = ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "JPM", "V"];

  return { companies, byTicker, watchlist, YEARS, priceSeries, yearSeries, mulberry32 };
})();
