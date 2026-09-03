import { useCountUp, useReveal } from "./hooks";

function Reveal({ children, delay = 0, className = "" }) {
  const ref = useReveal();
  return (
    <div ref={ref} className={`reveal ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

function Stat({ value, label, decimals = 0, prefix = "", suffix = "" }) {
  const shown = useCountUp(value, { decimals });
  return (
    <div className="stat">
      <div className="stat-v grad-text">
        {prefix}
        {Number(shown).toLocaleString("en-IN", {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })}
        {suffix}
      </div>
      <div className="stat-l">{label}</div>
    </div>
  );
}

const FEATURES = [
  {
    icon: "🧮",
    title: "A real index, not a line chart",
    body: "Fixed-weight geometric Laspeyres — the same index-number family ONS and Eurostat use for web-collected prices. Base period is the geometric mean of the first seven days, computed per stratum.",
  },
  {
    icon: "🎯",
    title: "The product is held constant",
    body: "We price route × airline × days-to-departure. Every day we ask for departures exactly D days out, so today's fare is comparable to last week's — instead of comparing a last-minute seat to an early bird.",
  },
  {
    icon: "🧹",
    title: "CPI-standard data quality",
    body: "Short gaps are imputed from sibling strata, long gaps drop out and renormalise the weights, and outliers are winsorised at 3σ rather than deleted. Every touched value stays flagged.",
  },
  {
    icon: "🔍",
    title: "Provenance you can audit",
    body: "Imputed and winsorised values carry their flags all the way to this screen. A statistical agency will not adopt an index that cannot separate observed from modelled numbers.",
  },
  {
    icon: "🛡️",
    title: "Compliance enforced in code",
    body: "Every source is gated on its robots.txt before a single fare request is made. Blocked means blocked — coverage shrinks, and nothing is invented to cover the gap.",
  },
  {
    icon: "🔌",
    title: "Source-agnostic by design",
    body: "Each platform is one adapter behind one interface. Swapping scraping for a formal data-sharing feed changes the parser and nothing else in the pipeline.",
  },
];

const STEPS = [
  { n: "1", t: "Collect", d: "Query fixed horizons — 3 to 60 days out — across every route and airline in scope.", c: "adapters/" },
  { n: "2", t: "Reduce", d: "Collapse all flights in a stratum to one price a day: the minimum fare, with the median alongside.", c: "strata.py" },
  { n: "3", t: "Clean", d: "Impute short gaps, winsorise outliers at 3σ, and flag every value that was touched.", c: "clean.py" },
  { n: "4", t: "Aggregate", d: "Weight by route, airline and horizon, then combine in log space into one index number.", c: "index.py" },
  { n: "5", t: "Serve", d: "Publish the index, its sub-indices and the underlying strata as JSON.", c: "api.py" },
];

export default function Landing({ data }) {
  const strataCount = data?.strata?.length ?? 0;
  const uniformDev = data?.sensitivity?.max_abs_deviation?.uniform ?? 0;

  return (
    <>
      <header className="hero container">
        <Reveal>
          <span className="badge">
            <span className="dot" />
            SIH 2026 · PS 26056 · MoSPI
          </span>
        </Reveal>

        <Reveal delay={80}>
          <h1>
            A daily airfare index
            <br />
            India&apos;s CPI could <span className="grad-text">actually adopt</span>
          </h1>
        </Reveal>

        <Reveal delay={160}>
          <p className="sub">
            Airfares move every day; CPI collection does not. APIx turns public economy fares into a
            statistically defensible daily price index for the Transport &amp; Communication
            sub-group — built on real index-number methodology, not a moving average of scraped
            prices.
          </p>
        </Reveal>

        <Reveal delay={240}>
          <div className="hero-cta">
            <a className="btn btn-primary" href="#dashboard">
              Explore the live index →
            </a>
            <a className="btn btn-ghost" href="#how">
              How it works
            </a>
          </div>
        </Reveal>

        <Reveal delay={320}>
          <div className="stat-strip">
            <Stat value={42} label="Micro-strata priced daily" />
            <Stat value={strataCount} label="Stratum-days in the panel" />
            <Stat value={7} label="Days-to-departure horizons" />
            <Stat value={uniformDev} label="Index pts of weight sensitivity" decimals={2} />
          </div>
        </Reveal>
      </header>

      <section className="block container" id="why">
        <Reveal>
          <div className="sec-head">
            <span className="eyebrow">The problem</span>
            <h2>DGCA reports traffic, months late. CPI needs fares, now.</h2>
            <p>
              Air travel is one of the most volatile items in the consumer basket, and the one a
              monthly collection cycle is worst at capturing. The data that does exist covers
              passenger volumes rather than prices, and arrives too late to inform a monthly index.
            </p>
          </div>
        </Reveal>
        <div className="grid-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 70}>
              <article
                className="feature"
                onMouseMove={(e) => {
                  const r = e.currentTarget.getBoundingClientRect();
                  e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
                  e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
                }}
              >
                <div className="ico">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="block container" id="how">
        <Reveal>
          <div className="sec-head">
            <span className="eyebrow">How it works</span>
            <h2>Five stages, one number</h2>
            <p>
              A fixed pipeline where cleaning always precedes computation — an index is never
              calculated over unclean data and patched afterwards.
            </p>
          </div>
        </Reveal>
        <div className="steps">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 70}>
              <div className="step">
                <div className="n">{s.n}</div>
                <h4>{s.t}</h4>
                <p>{s.d}</p>
                <code>{s.c}</code>
              </div>
            </Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
