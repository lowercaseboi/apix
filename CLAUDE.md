# CLAUDE.md

Operating instructions for Claude Code in the APIx repository.

## What this is

APIx is an automated daily airfare price index for India, built for MoSPI's Data Informatics and Innovation Division (SIH 2026, PS 26056). It collects public economy fares from booking platforms, normalizes them into comparable statistical units, and publishes a weighted price index intended as a high-frequency input to the CPI Transport and Communication sub-group.

Full requirements live in `docs/APIx_PRD_and_Dev_Plan.md`. Read it before making architectural changes.

## Context: this is a 3-hour hackathon build

Bias hard toward working code over clean code.

- Do not refactor working code unless it is blocking the current task.
- Do not add dependencies without asking. `numpy`, `pandas`, `fastapi`, `httpx`, `playwright`, `pydantic` are already in. Anything else needs a reason.
- Do not add abstraction layers "for later." There is no later.
- Do not write tests for UI or scrapers. Do write tests for `index.py` — see Testing.
- If something is timeboxed in the plan and the box is spent, say so and propose the fallback rather than continuing.

## Frozen decisions — do not change these

These were locked at T+0 by the whole team. If a change seems necessary, stop and flag it rather than editing.

**Scope.** 3 routes (DEL–BOM, DEL–BLR, BOM–BLR), 2 airlines (6E, SG), 2 platforms (Ixigo, EaseMyTrip), 7 horizons (3, 7, 14, 21, 30, 45, 60 days), base economy only. 42 micro-strata total. Do not add routes, airlines, or cabins even if trivial.

**The priced product is `route × airline × days-to-departure`.** This is the core methodological decision. Days-to-departure is held constant across time so successive observations are comparable. Never write code that compares fares across different horizons as though they were the same product.

**Collection queries fixed horizons, not date windows.** The scraper asks for departures at exactly D days ahead, every day. It does not sweep a range of departure dates.

**`FareRecord` is the contract.** Every module codes against it. Changing it means coordinating with three other people.

```python
@dataclass(frozen=True)
class FareRecord:
    route: str            # "DEL-BOM"
    airline: str          # "6E" | "SG"
    dep_date: date
    scrape_ts: datetime   # UTC
    horizon: int          # 3|7|14|21|30|45|60
    flight_no: str
    fare_inr: float       # base fare + statutory taxes, no add-ons
    fare_class: str       # "economy"
    source: str           # "ixigo" | "easemytrip"
    is_imputed: bool = False
    is_winsorized: bool = False
```

## Architecture

```
src/
  schema.py     FareRecord, stratum key helpers
  seed.py       Synthetic panel generator (also serves as backfill module)
  adapters/     One class per platform, all implementing FareSource
  strata.py     Raw records -> stratum prices (min primary, median secondary)
  clean.py      Imputation + winsorizing. Runs BEFORE index.py
  weights.py    Three weight vectors, loaded from config/weights.yaml
  index.py      Base period + aggregation formula + sub-indices
  api.py        FastAPI: /index, /index/route/{r}, /index/horizon-band/{b}, /strata, /anomalies
dashboard/      React front-end
config/
  weights.yaml  Route, airline, horizon weights
```

Pipeline order is fixed: `adapters -> strata -> clean -> index`. Cleaning always precedes index computation. Never compute an index over unclean data and patch afterward.

## Index invariants

The formula is a fixed-weight geometric Laspeyres:

```
APIx(t) = 100 * exp( Σ_r w_r Σ_d w_d Σ_a w_a * ln( p[r,a,d](t) / p̄[r,a,d](0) ) )
```

Implemented as one contraction:

```python
log_rel = np.log(prices / base_prices)          # shape (R, D, A)
apix = 100 * np.exp(np.einsum('r,d,a,rda->', w_r, w_d, w_a, log_rel))
```

Hold these invariants. Violating any of them silently corrupts the index:

- **Geometric, never arithmetic.** All aggregation happens in log space. If you find yourself writing `np.mean` on prices, it is wrong.
- **Base period is the geometric mean of the first 7 days**, not a single day.
- **Weights are fixed and each vector sums to 1.** `weights.py` must assert this on load.
- **No randomness anywhere in the index path.** Same raw table plus same config must give a bit-identical result. `seed.py` may use RNG but must accept and record a fixed seed.
- **Missing prices are never zero and never carried forward indefinitely.** Gaps ≤3 days get overall mean imputation from sibling strata (same route, other horizons). Gaps >3 days get dropped with the affected weight vector renormalized.
- **Outliers are winsorized at 3σ of the stratum's own day-over-day log-relative distribution, not dropped.** Dropping creates a gap that then needs imputing, compounding the intervention.
- **Provenance flags are mandatory.** Any imputed or winsorized value carries `is_imputed` / `is_winsorized` through to the API and the dashboard. A statistical agency will not adopt an index that cannot separate observed from modelled values.

Sub-indices reuse the same function with restricted weight vectors — one-hot for route or airline, horizon-band subsets for the advance-purchase spread. Do not write a second aggregation implementation.

## Scraping constraints

Non-negotiable, and they are also our answer to the judges:

- Respect `robots.txt`. Rate-limit well below normal human browsing volume.
- Public fare displays only. No login, no paywall circumvention, no auth bypass.
- No personal data collected, stored, or processed, ever.
- Never initiate a booking, hold, or transaction of any kind.
- Identify the agent honestly in the user-agent string.
- Publish only derived aggregates. Never commit or expose raw scraped fare tables.

If a task appears to require violating any of these, stop and say so.

## Adding a platform

Write one adapter in `src/adapters/` implementing the `FareSource` interface and returning `FareRecord` objects. Register it in the adapter registry. Touch nothing else — the index engine is source-agnostic by design, and that property is part of the pitch.

## Testing

`index.py` is the only module that gets real tests, because a subtle error there is invisible on the dashboard and fatal in the pitch. Test at minimum:

- A flat panel (all prices constant) returns exactly 100.0.
- A uniform 10% price rise across all strata returns 110.0.
- Weight vectors that do not sum to 1 raise on load.
- Removing a stratum renormalizes weights correctly and does not shift the index for unchanged strata.

```bash
pytest tests/test_index.py -q
```

## Commands

```bash
uvicorn src.api:app --reload      # API on :8000
python -m src.seed --days 90      # generate synthetic panel
python -m src.collect             # run one collection cycle
cd dashboard && npm run dev       # dashboard on :5173
```

## Honesty rules for output

The pitch depends on not overclaiming, so the code and its comments should not overclaim either.

- Anomaly detection is a z-score. The forecast is a linear or ARIMA baseline. Label them as such in code and UI. Do not call them "AI-powered."
- Horizon weights are an assumed prior, not measured data. `config/weights.yaml` must carry a comment saying so.
- Synthetic backfill data must be visibly distinguishable from observed data at every layer, including the dashboard.
- Never fabricate statistics, benchmark numbers, or impact figures in code comments, docs, or UI copy.
