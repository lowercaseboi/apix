import { useEffect, useRef, useState } from "react";

export const API_BASE = "http://localhost:8000";

// Mirrors src/schema.py's frozen scope — there is no /routes or /airlines endpoint.
export const ROUTES = ["DEL-BOM", "DEL-BLR", "BOM-BLR"];
export const AIRLINES = ["6E", "SG"];
export const AIRLINE_NAMES = { "6E": "IndiGo", SG: "SpiceJet" };
export const ROUTE_COLORS = { "DEL-BOM": "#6366f1", "DEL-BLR": "#22d3ee", "BOM-BLR": "#f472b6" };
export const AIRLINE_COLORS = { "6E": "#a855f7", SG: "#fbbf24" };
export const SCENARIO_COLORS = {
  config: "#6366f1",
  uniform: "#34d399",
  front_loaded: "#fbbf24",
  back_loaded: "#fb7185",
};
export const SCENARIO_LABELS = {
  config: "Config (declining prior)",
  uniform: "Uniform 1/7",
  front_loaded: "Front-loaded",
  back_loaded: "Back-loaded",
};

const json = (path) =>
  fetch(`${API_BASE}${path}`).then((r) => {
    if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
    return r.json();
  });

export function mergeSeriesByDate(seriesByKey, keys) {
  const byDate = {};
  for (const key of keys) {
    for (const point of seriesByKey[key] || []) {
      byDate[point.date] = byDate[point.date] || { date: point.date };
      byDate[point.date][key] = point.value;
    }
  }
  return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
}

export function useApiData() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.all([
      json("/index"),
      ...ROUTES.map((r) => json(`/index/route/${r}`)),
      ...AIRLINES.map((a) => json(`/index/airline/${a}`)),
      json("/strata"),
      json("/anomalies"),
      json("/sources"),
      json("/sensitivity"),
      json("/forecast"),
    ])
      .then(([headline, ...rest]) => {
        if (!alive) return;
        const n = ROUTES.length;
        const m = AIRLINES.length;
        const strata = rest[n + m];

        const latestDay = strata.reduce((mx, r) => (r.scrape_day > mx ? r.scrape_day : mx), "");

        setData({
          headline,
          routes: mergeSeriesByDate(Object.fromEntries(ROUTES.map((r, i) => [r, rest[i]])), ROUTES),
          airlines: mergeSeriesByDate(
            Object.fromEntries(AIRLINES.map((a, i) => [a, rest[n + i]])),
            AIRLINES
          ),
          strata,
          latestDay,
          anomalies: rest[n + m + 1],
          sources: rest[n + m + 2],
          sensitivity: rest[n + m + 3],
          forecast: rest[n + m + 4],
        });
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  return { data, error };
}

/** Builds the days-to-departure fare curve for the latest day, filtered. */
export function buildFareCurve(strata, latestDay, { routes, airlines, metric }) {
  const sum = {};
  const count = {};
  for (const row of strata) {
    if (row.scrape_day !== latestDay) continue;
    if (routes.length && !routes.includes(row.route)) continue;
    if (airlines.length && !airlines.includes(row.airline)) continue;
    const v = metric === "median" ? row.median_fare : row.min_fare;
    if (v == null) continue;
    sum[row.horizon] = (sum[row.horizon] || 0) + v;
    count[row.horizon] = (count[row.horizon] || 0) + 1;
  }
  return Object.keys(sum)
    .map(Number)
    .sort((a, b) => b - a) // 60 → 3, departure approaching left to right
    .map((h) => ({ horizon: `${h}d`, fare: Math.round(sum[h] / count[h]) }));
}

export function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!("IntersectionObserver" in window)) {
      el.classList.add("in");
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}

export function useCountUp(target, { duration = 1100, decimals = 0 } = {}) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target == null || Number.isNaN(target)) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value.toFixed(decimals);
}
