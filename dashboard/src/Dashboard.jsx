import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AIRLINES,
  AIRLINE_COLORS,
  AIRLINE_NAMES,
  ROUTES,
  ROUTE_COLORS,
  SCENARIO_COLORS,
  SCENARIO_LABELS,
  buildFareCurve,
  useReveal,
} from "./hooks";

const shortDate = (d) =>
  new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function Tip({ active, payload, label, unit = "", decimals = 2 }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tt">
      <div className="tt-d">{label}</div>
      {payload
        .filter((p) => p.value != null)
        .map((p) => (
          <div className="tt-r" key={p.dataKey}>
            <span className="swatch" style={{ background: p.color, width: 8, height: 8, borderRadius: 4 }} />
            <span>{p.name}</span>
            <b style={{ color: p.color }}>
              {unit}
              {Number(p.value).toLocaleString("en-IN", {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals,
              })}
            </b>
          </div>
        ))}
    </div>
  );
}

function Panel({ title, subtitle, actions, children, delay = 0 }) {
  const ref = useReveal();
  return (
    <div ref={ref} className="reveal panel" style={{ transitionDelay: `${delay}ms` }}>
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}

function Chips({ items, active, onToggle, colors, labels }) {
  return (
    <div className="chips">
      {items.map((k) => {
        const on = active.includes(k);
        return (
          <button
            key={k}
            className={`chip ${on ? "on" : ""}`}
            style={on ? { "--chip-c": colors?.[k], background: colors?.[k], color: "#080a12" } : undefined}
            onClick={() => onToggle(k)}
            aria-pressed={on}
          >
            {colors && <span className="swatch" style={{ background: on ? "#080a12" : colors[k] }} />}
            {labels?.[k] ?? k}
          </button>
        );
      })}
    </div>
  );
}

export default function Dashboard({ data }) {
  const [activeRoutes, setActiveRoutes] = useState(ROUTES);
  const [activeAirlines, setActiveAirlines] = useState(AIRLINES);
  const [metric, setMetric] = useState("min");
  const [scenarios, setScenarios] = useState(Object.keys(SCENARIO_COLORS));

  const toggle = (list, setList, key) =>
    setList(list.includes(key) ? list.filter((k) => k !== key) : [...list, key]);

  const fareCurve = useMemo(
    () =>
      buildFareCurve(data.strata, data.latestDay, {
        routes: activeRoutes,
        airlines: activeAirlines,
        metric,
      }),
    [data.strata, data.latestDay, activeRoutes, activeAirlines, metric]
  );

  const forecastChart = useMemo(() => {
    const f = data.forecast;
    const rows = [
      ...f.recent.map((p) => ({ date: p.date, observed: p.value })),
      ...f.projection.map((p) => ({ date: p.date, projected: p.value })),
    ];
    const last = f.recent[f.recent.length - 1];
    const join = rows.find((r) => r.date === last.date);
    if (join) join.projected = last.value;
    return rows;
  }, [data.forecast]);

  const sensitivityData = useMemo(() => {
    const byDate = {};
    for (const [name, series] of Object.entries(data.sensitivity.series)) {
      for (const p of series) {
        byDate[p.date] = byDate[p.date] || { date: p.date };
        byDate[p.date][name] = p.value;
      }
    }
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
  }, [data.sensitivity]);

  const latest = data.headline[data.headline.length - 1];
  const first = data.headline[0];
  const change = ((latest.value - first.value) / first.value) * 100;

  const axis = { tick: { fontSize: 11 }, tickLine: false, axisLine: false };

  return (
    <section className="block container" id="dashboard">
      <div className="sec-head">
        <span className="eyebrow">Live index</span>
        <h2>The index, and everything under it</h2>
        <p>
          Filter by route and airline, switch the stratum price rule, and drill into the anomalies —
          every chart reads from the same API the pipeline publishes.
        </p>
      </div>

      <Panel
        title="Headline APIx"
        subtitle={`Fixed-weight geometric Laspeyres across all 42 strata. Base period = 100. Latest: ${latest.value.toFixed(2)} (${change >= 0 ? "+" : ""}${change.toFixed(2)}% since base).`}
        actions={
          <span className={`pill ${change >= 0 ? "pill-warn" : "pill-ok"}`}>
            {change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
          </span>
        }
      >
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data.headline} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="gHead" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axis} />
            <YAxis domain={["auto", "auto"]} {...axis} />
            <Tooltip content={<Tip />} />
            <ReferenceLine y={100} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
            <Area
              type="monotone"
              dataKey="value"
              name="APIx"
              stroke="#6366f1"
              strokeWidth={2.5}
              fill="url(#gHead)"
              animationDuration={1100}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>

      <div className="grid-2">
        <Panel
          title="By route"
          subtitle="One-hot route sub-indices. Click a route to show or hide it."
          actions={
            <Chips
              items={ROUTES}
              active={activeRoutes}
              onToggle={(k) => toggle(activeRoutes, setActiveRoutes, k)}
              colors={ROUTE_COLORS}
            />
          }
        >
          <ResponsiveContainer width="100%" height={270}>
            <LineChart data={data.routes} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axis} />
              <YAxis domain={["auto", "auto"]} {...axis} />
              <Tooltip content={<Tip />} />
              <ReferenceLine y={100} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
              {ROUTES.filter((r) => activeRoutes.includes(r)).map((r) => (
                <Line
                  key={r}
                  type="monotone"
                  dataKey={r}
                  name={r}
                  stroke={ROUTE_COLORS[r]}
                  strokeWidth={2}
                  dot={false}
                  animationDuration={900}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Panel>

        <Panel
          title="By airline"
          subtitle="One-hot airline sub-indices across all routes and horizons."
          actions={
            <Chips
              items={AIRLINES}
              active={activeAirlines}
              onToggle={(k) => toggle(activeAirlines, setActiveAirlines, k)}
              colors={AIRLINE_COLORS}
              labels={AIRLINE_NAMES}
            />
          }
        >
          <ResponsiveContainer width="100%" height={270}>
            <LineChart data={data.airlines} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axis} />
              <YAxis domain={["auto", "auto"]} {...axis} />
              <Tooltip content={<Tip />} />
              <ReferenceLine y={100} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
              {AIRLINES.filter((a) => activeAirlines.includes(a)).map((a) => (
                <Line
                  key={a}
                  type="monotone"
                  dataKey={a}
                  name={AIRLINE_NAMES[a]}
                  stroke={AIRLINE_COLORS[a]}
                  strokeWidth={2}
                  dot={false}
                  animationDuration={900}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title="Days-to-departure fare curve"
        subtitle={`Average fare in rupees on ${data.latestDay} — a price level, not an index. Reflects the route and airline filters above.`}
        actions={
          <div className="chips">
            {["min", "median"].map((m) => (
              <button
                key={m}
                className={`chip ${metric === m ? "on" : ""}`}
                style={metric === m ? { background: "#22d3ee", color: "#080a12" } : undefined}
                onClick={() => setMetric(m)}
                aria-pressed={metric === m}
              >
                {m === "min" ? "Minimum fare" : "Median fare"}
              </button>
            ))}
          </div>
        }
      >
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={fareCurve} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="gBar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22d3ee" />
                <stop offset="100%" stopColor="#6366f1" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="horizon" {...axis} />
            <YAxis tickFormatter={(v) => `₹${(v / 1000).toFixed(1)}k`} {...axis} />
            <Tooltip content={<Tip unit="₹" decimals={0} />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
            <Bar
              dataKey="fare"
              name={metric === "min" ? "Min fare" : "Median fare"}
              fill="url(#gBar)"
              radius={[6, 6, 0, 0]}
              animationDuration={900}
            />
          </BarChart>
        </ResponsiveContainer>
        <p className="legend-note">
          Fares climb steeply as departure approaches — which is exactly why the index holds
          days-to-departure constant. A fare is only comparable to another fare bought the same
          distance from takeoff.
        </p>
      </Panel>

      <Panel
        title="Weight sensitivity"
        subtitle="Horizon weights are the one assumed prior in the index, so they are the one vector stress-tested. Toggle a scenario to compare."
        actions={
          <Chips
            items={Object.keys(SCENARIO_COLORS)}
            active={scenarios}
            onToggle={(k) => toggle(scenarios, setScenarios, k)}
            colors={SCENARIO_COLORS}
            labels={SCENARIO_LABELS}
          />
        }
      >
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={sensitivityData} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axis} />
            <YAxis domain={["auto", "auto"]} {...axis} />
            <Tooltip content={<Tip />} />
            <ReferenceLine y={100} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
            {Object.keys(SCENARIO_COLORS)
              .filter((s) => scenarios.includes(s))
              .map((s) => (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  name={SCENARIO_LABELS[s]}
                  stroke={SCENARIO_COLORS[s]}
                  strokeWidth={s === "config" ? 2.5 : 1.6}
                  strokeDasharray={s === "config" ? undefined : "5 4"}
                  dot={false}
                  animationDuration={900}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
        <p className="legend-note">
          Replacing the assumed declining prior with uniform 1/7 weights moves the index by at most{" "}
          <b>{data.sensitivity.max_abs_deviation.uniform.toFixed(2)} index points</b> across the
          whole series — the prescribed robustness check. The two tilts are illustrative extremes,
          not part of it.
        </p>
      </Panel>

      <Panel
        title="7-day baseline projection"
        subtitle="OLS trend plus day-of-week effects, fitted on the recent index and extended forward. A baseline statistical model — not machine learning."
        actions={
          <span className={`pill ${data.forecast.backtest?.backtest_ratio < 1 ? "pill-ok" : "pill-bad"}`}>
            {data.forecast.backtest?.backtest_ratio < 1 ? "BEATS NAIVE BASELINE" : "WORSE THAN NAIVE"}
          </span>
        }
      >
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={forecastChart} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axis} />
            <YAxis domain={["auto", "auto"]} {...axis} />
            <Tooltip content={<Tip />} />
            <ReferenceLine y={100} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
            <Line
              type="monotone"
              dataKey="observed"
              name="Index"
              stroke="#6366f1"
              strokeWidth={2.5}
              dot={false}
              animationDuration={900}
            />
            <Line
              type="monotone"
              dataKey="projected"
              name="Projection"
              stroke="#a855f7"
              strokeWidth={2}
              strokeDasharray="6 5"
              dot={{ r: 2.5, fill: "#a855f7" }}
              animationDuration={900}
            />
          </LineChart>
        </ResponsiveContainer>
        <p className="legend-note">
          Trend <b>{data.forecast.slope_per_day >= 0 ? "+" : ""}{data.forecast.slope_per_day.toFixed(4)}</b>{" "}
          index points/day over {data.forecast.window_days} days, plus a Saturday/Sunday premium of{" "}
          <b>+{data.forecast.weekday_effects_vs_monday?.Sat?.toFixed(2)}</b> index points vs. Monday.
          In-sample residual σ = <b>{data.forecast.residual_std.toFixed(2)}</b> —{" "}
          {data.forecast.residual_std_note}
        </p>
        {data.forecast.backtest && (
          <p className="legend-note">
            <b>Backtested</b> on a held-out {data.forecast.backtest.holdout_days}-day window: this
            model scores {data.forecast.backtest.model_mae.toFixed(3)} mean absolute error, versus{" "}
            {data.forecast.backtest.naive_no_change_mae.toFixed(3)} for assuming nothing changes —{" "}
            {(1 / data.forecast.backtest.backtest_ratio).toFixed(1)}× more accurate than the naive
            baseline. Published so the claim is checkable, not asserted.
          </p>
        )}
      </Panel>

      <div className="grid-2">
        <Panel
          title="Collection coverage"
          subtitle="Every source is gated on its robots.txt before any fare request is made."
        >
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Platform</th>
                  <th>robots.txt</th>
                  <th>Queries</th>
                  <th>Records</th>
                </tr>
              </thead>
              <tbody>
                {data.sources.sources.map((s) => (
                  <tr key={s.source}>
                    <td className="strong mono">{s.source}</td>
                    <td>
                      <span className={`pill ${s.robots_allowed ? "pill-ok" : "pill-bad"}`}>
                        {s.robots_allowed === null ? "UNCHECKED" : s.robots_allowed ? "ALLOWED" : "BLOCKED"}
                      </span>
                    </td>
                    <td className="mono">{s.queries_attempted ?? 0}</td>
                    <td className="mono">{s.records_collected ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="legend-note">
            Both portals disallow their fare-search paths, so no live fares were collected and none
            were fabricated to fill the gap. Every figure on this page comes from a labelled
            synthetic backfill panel.
          </p>
        </Panel>

        <Panel
          title="Anomaly panel"
          subtitle="Stratum-days winsorised at 3σ of their own day-over-day log-relative distribution, shown raw beside adjusted."
        >
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Stratum</th>
                  <th>Raw</th>
                  <th>Adjusted</th>
                </tr>
              </thead>
              <tbody>
                {data.anomalies.length === 0 && (
                  <tr>
                    <td colSpan={4}>No anomalies flagged.</td>
                  </tr>
                )}
                {data.anomalies.map((a, i) => (
                  <tr key={i}>
                    <td className="mono">{a.scrape_day}</td>
                    <td className="strong mono">
                      {a.route} · {a.airline} · {a.horizon}d
                    </td>
                    <td className="mono">₹{a.raw_fare_inr.toFixed(0)}</td>
                    <td className="mono" style={{ color: "#34d399" }}>
                      ₹{a.adjusted_fare_inr.toFixed(0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="legend-note">
            Outliers are <b>clipped, never dropped</b> — deleting one would create a gap that then
            needs imputing, compounding the intervention.
          </p>
        </Panel>
      </div>
    </section>
  );
}
