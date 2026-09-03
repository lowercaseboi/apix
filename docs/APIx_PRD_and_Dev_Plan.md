# APIx — Product Requirements Document & Hackathon Development Plan

**Project:** Automated Real-Time Airfare Price Index for India
**Team:** Develarpers
**Event:** Smart India Hackathon 2026
**Problem Statement ID:** 26056
**Ministry:** MoSPI — Data Informatics and Innovation Division (DIID)
**Document scope:** 3-hour prototype build
**Status:** Active build document

---

## Part 1 — Product Requirements Document

### 1.1 Problem statement

India's Consumer Price Index includes air transport within the Transport and Communication sub-group, but the underlying fare data reaches NSO with a substantial lag and at low frequency. DGCA publishes route-level traffic monthly; airline fare data is not collected continuously. Meanwhile, domestic airfares are set by dynamic pricing engines that change prices many times a day.

The result is a measurement gap. A price series that updates monthly cannot represent a market that reprices hourly, and neither NSO nor RBI currently has a high-frequency read on air transport inflation.

APIx closes that gap by collecting fares directly from public booking surfaces on a fixed daily schedule, normalizing them into comparable statistical units, and publishing a weighted price index built on standard index-number theory.

### 1.2 What we are building in this session

A working end-to-end prototype: scraper → normalized store → index engine → API → dashboard, covering a deliberately narrow slice of the market.

**This is a vertical slice, not a demo mock-up.** Every layer is real and every layer is thin. The architecture is designed so that widening the slice is configuration, not rewriting.

### 1.3 Scope for the prototype

| Dimension | Value | Count |
|---|---|---|
| Routes | DEL–BOM, DEL–BLR, BOM–BLR | 3 |
| Airlines | IndiGo (6E), SpiceJet (SG) | 2 |
| Platforms | Ixigo (primary), EaseMyTrip (cross-check) | 2 |
| Booking horizons | 3, 7, 14, 21, 30, 45, 60 days ahead | 7 |
| Cabin | Base economy, 1 adult, one-way, no add-ons | 1 |
| **Micro-strata** | 3 × 2 × 7 | **42** |

Daily scrape volume: 3 routes × 7 horizons × 2 platforms = **42 queries/day**. Each query returns fares for both airlines. This is small enough to complete in minutes and to run politely with generous rate limiting.

**Explicitly out of scope for the prototype:** international routes, business/premium cabins, round-trip and multi-city, connecting itineraries, refundable vs non-refundable fare distinctions, baggage-inclusive fare variants, and the remaining eight OTAs and three airlines named in the full proposal.

### 1.4 The central design decision

An airfare is not a fixed product. The same DEL–BOM seat costs one price 45 days before departure and a very different price 2 days before. If the index compares "today's average scraped fare" with "yesterday's average scraped fare," it measures **booking timing**, not **price change**.

Therefore the priced product is defined as:

> **route × airline × days-to-departure**

Days-to-departure is held constant across time, so successive observations are genuinely comparable. This mirrors how BLS and Eurostat treat airfares in their national CPIs.

**Consequence for collection:** the scraper does not sweep a window of departure dates. Every day it queries departures at exactly D = {3, 7, 14, 21, 30, 45, 60} days ahead. This produces a balanced panel by construction.

### 1.5 Users and their needs

| User | Need | What APIx gives them |
|---|---|---|
| MoSPI / NSO statistician | High-frequency input to the CPI Transport sub-group | Daily index with documented, reproducible methodology |
| RBI analyst | Early signal on transport-driven inflation | Index published with same-day latency |
| Policy researcher | Evidence on dynamic pricing behaviour | Advance-purchase spread indices and route-level series |
| Public / press | Transparency on fare movement | Public dashboard with route filters |

### 1.6 Functional requirements

**FR-1 — Scheduled collection.** Collect base economy fares for all 42 strata once daily at a fixed clock time. Fixed timing matters: fares vary intraday, so a drifting collection time injects noise into the index.

**FR-2 — Normalization.** Convert heterogeneous platform responses into a single canonical `FareRecord`. Strip convenience fees and platform-specific discount coupons so the recorded price is the base fare plus statutory taxes only.

**FR-3 — Stratum reduction.** Collapse all flights for a given (route, airline, departure date) into one representative price. Primary rule: minimum available fare. Secondary rule computed in parallel: median fare.

**FR-4 — Index computation.** Produce a daily index value using the formula in §1.9, plus route-level, airline-level, and horizon-band sub-indices.

**FR-5 — Data quality handling.** Detect and treat missing observations and outliers per §1.10 before the index is computed.

**FR-6 — API.** Serve index series and underlying strata over HTTP as JSON.

**FR-7 — Dashboard.** Display the headline index time series, route comparison, airline comparison, the days-to-departure fare curve, and flagged anomalies.

**FR-8 — Historical backfill.** Generate a calibrated synthetic panel covering the period before live collection began, clearly labelled as modelled rather than observed.

### 1.7 Non-functional requirements

- **Reproducibility.** Given the same raw fare table and the same weight configuration, the index must be bit-identical on re-run. No randomness in the index path.
- **Auditability.** Every published index value must be traceable to the exact set of stratum prices that produced it.
- **Politeness.** Respect `robots.txt`. Rate-limit to well below the platform's normal human traffic. Identify the agent honestly. No booking automation, no authentication bypass, no PII collection.
- **Source-agnosticism.** Adding a platform must mean writing one adapter class, not touching the index engine.
- **Graceful degradation.** A failed platform, a failed route, or a failed day must reduce coverage — never crash the pipeline or silently corrupt the index.

### 1.8 Data model

```python
@dataclass(frozen=True)
class FareRecord:
    route: str            # "DEL-BOM"
    airline: str          # "6E" | "SG"
    dep_date: date        # departure date
    scrape_ts: datetime   # when observed (UTC)
    horizon: int          # days to departure: 3|7|14|21|30|45|60
    flight_no: str
    fare_inr: float       # base fare + statutory taxes, no add-ons
    fare_class: str       # "economy"
    source: str           # "ixigo" | "easemytrip"
    is_imputed: bool = False
    is_winsorized: bool = False
```

Stratum key: `(route, airline, horizon)` → 42 unique keys.

The two provenance flags are not optional decoration. Any value that was imputed or winsorized must be visibly marked, in the store and on the dashboard. A statistical agency will not adopt an index that cannot distinguish observed from modelled values.

### 1.9 Index methodology

**Step A — Stratum price.** For route `r`, airline `a`, horizon `d`, on scrape day `t`:

```
p[r,a,d](t) = min over all economy flights f of fare[f]
```

Minimum available fare is the consumer-relevant price. The median across flights is computed simultaneously as a robustness variant and exposed on the dashboard as a toggle.

**Step B — Base period.** The base is the geometric mean of the first seven days of the series, not a single day. A single-day base makes the entire index hostage to one noisy scrape.

```
p̄[r,a,d](0) = exp( (1/7) · Σ_{t=1..7} ln p[r,a,d](t) )
```

**Step C — Aggregation.** Three nested stages — across airlines, across horizons, across routes — each a weighted geometric mean. Because all three are geometric, they collapse algebraically into a single expression:

```
                    ⎛                                     p[r,a,d](t)  ⎞
APIx(t) = 100 × exp ⎜  Σ  w_r  Σ  w_d  Σ  w_a  ·  ln  ───────────────  ⎟
                    ⎝  r        d        a             p̄[r,a,d](0)    ⎠

subject to   Σ w_r = Σ w_d = Σ w_a = 1
```

This is a **fixed-weight geometric Laspeyres** index. The elementary form — geometric mean of price relatives — is the **Jevons index**.

Two properties to state explicitly in the pitch:

1. **Geometric rather than arithmetic.** Airfare distributions are heavily right-skewed with occasional extreme values. The geometric mean is far less distorted by them. ONS and Eurostat both use Jevons for web-collected prices.
2. **Fixed weights, fixed base.** This avoids chain drift, a real pathology in high-frequency indices where prices oscillate rather than trend.

Implementation is a single tensor contraction:

```python
log_rel = np.log(prices / base_prices)          # shape (R, D, A)
apix = 100 * np.exp(np.einsum('r,d,a,rda->', w_r, w_d, w_a, log_rel))
```

### 1.10 Data quality rules

**Missing observations**

| Gap length | Treatment | Justification |
|---|---|---|
| ≤ 3 days | Overall mean imputation — apply the average log-relative of sibling strata (same route, other horizons) | Standard CPI practice for temporarily unavailable items |
| > 3 days | Drop the stratum for those days and renormalize the affected weight vector to sum to 1 | Prevents a long stale value from anchoring the index |

A missing price is never treated as zero and never carried forward indefinitely.

**Outliers**

Compute the day-over-day log relative for each stratum:

```
Δ[r,a,d](t) = ln p(t) − ln p(t−1)
```

Flag observations where `|Δ| > 3σ` of that stratum's own historical Δ distribution. **Winsorize at the 3σ bound rather than dropping** — dropping creates a gap that then requires imputation, compounding the intervention.

All flagged observations surface on the dashboard's anomaly panel with the raw and adjusted values shown side by side.

### 1.11 Weights

Three vectors are required. Source real figures where they exist; label assumptions honestly where they do not.

**Route weights `w_r`** — DGCA publishes monthly domestic city-pair passenger traffic. Take the most recent available month, extract the three routes, renormalize to sum to 1. This is the most defensible of the three weights and takes roughly ten minutes to source.

**Airline weights `w_a`** — two options: DGCA monthly domestic market share, or route-specific scheduled seat share computed from the scrape itself (flight frequency × typical aircraft capacity). The second is preferable because it is route-specific and self-contained.

**Horizon weights `w_d`** — no public Indian source exists for the domestic booking lead-time distribution. Use a declining prior reflecting that most domestic bookings occur close to departure:

| Horizon | 3d | 7d | 14d | 21d | 30d | 45d | 60d |
|---|---|---|---|---|---|---|---|
| Weight | 0.20 | 0.22 | 0.20 | 0.15 | 0.12 | 0.07 | 0.04 |

**This must be labelled on the methodology slide as an assumed prior pending a MoSPI booking-window survey.** Do not present it as measured.

Then run a sensitivity check: recompute the index with uniform horizon weights and show that the series barely moves. Demonstrating that the headline result is robust to the one weight you had to assume is a genuinely strong moment in a technical pitch, and it converts a weakness into evidence of rigour.

### 1.12 Sub-indices

Each costs nothing once the core formula exists — set the relevant weight vector to a one-hot or restricted form.

- **APIx headline** — full aggregate across all 42 strata.
- **Route indices** — one-hot `w_r`. Three series.
- **Airline indices** — one-hot `w_a`. Two series.
- **Advance-purchase indices** — a "≤7 day" index and a "≥30 day" index. The **spread between them is a direct measure of dynamic-pricing aggressiveness**, and it is very unlikely any competing team will have it.

### 1.13 Success criteria for the prototype

**Must have** (the demo fails without these)
- Live index rendering from real scraped data for at least one platform
- Correct implementation of the formula in §1.9 with all three weight vectors
- Dashboard showing headline index plus per-route breakdown
- A recorded video of the full working demo

**Should have**
- Both platforms collecting, with a cross-source consistency check
- Imputation and winsorizing active with provenance flags visible
- Advance-purchase spread index
- Weight sensitivity comparison

**Could have**
- 7-day index forecast
- Anomaly panel with drill-down
- Backfill series calibrated against DGCA published average fares

**Will not have this session**
- Authentication, multi-user accounts, persistent cloud deployment, any additional route/airline/platform beyond the scoped set

### 1.14 Legal and ethical position

Prepare this as a stated position, not an improvised answer:

- Only publicly displayed fare information is collected; no login, no paywall circumvention, no authentication bypass.
- `robots.txt` is respected. Requests are rate-limited well below normal human browsing volume.
- No personal data of any kind is collected, stored, or processed.
- No booking, hold, or transaction is ever initiated.
- Only derived statistical aggregates are published — never raw scraped fare tables — which is the same posture NSO takes with primary price collection.
- The system is designed for a government statistical agency, where formal data-sharing agreements with airlines would replace scraping in production. Scraping is the bootstrap, not the end state.

---

## Part 2 — Development Plan

### 2.1 Team allocation

| Person | Track | Owns |
|---|---|---|
| **P1** | Collection | Platform adapters, scheduler, rate limiting, raw store |
| **P2** | Index engine | Normalization, strata, weights, index formula, sub-indices, API |
| **P3** | Dashboard | All front-end, charts, filters, anomaly panel |
| **P4** | Narrative | Deck updates, screenshots, methodology slide, pitch rehearsal, Q&A prep |
| **P5** | Integration | Glue, deployment, ML garnish, demo recording, floating support |

P5 is deliberately kept off the critical path. When something breaks around T+120 — and something will — P5 is the person free to fix it without stalling another track.

### 2.2 T+0 to T+15 — All five, no code

Nothing gets typed in this window. This is what makes the parallel work possible.

1. **Say the demo sentence out loud.** "We show a live daily airfare index for three Indian city-pairs, built on the same index-number methodology NSO uses, that MoSPI could plug into the CPI Transport sub-group." Anything that does not serve that sentence is cut.
2. **Freeze `FareRecord`** exactly as written in §1.8. Paste it into the repo. Everyone codes against it from this moment.
3. **Freeze the scope table** in §1.3. No additions during the build, regardless of how easy something looks at T+90.
4. **Create the weight config file** with the §1.11 values as placeholders. P2 is now unblocked without waiting for anyone to source DGCA numbers.
5. **Repo, branches, and a shared channel for screenshots** so P4 can pull assets without interrupting anyone.

### 2.3 Module build order (P2's track)

Order matters. Each module either unblocks another track or makes the demo more robust — never both, so they can be dropped from the bottom without breaking anything above.

| # | Module | Purpose | Target |
|---|---|---|---|
| 1 | `schema.py` | `FareRecord`, stratum key helpers | T+20 |
| 2 | `seed.py` | Synthetic 90-day panel across all 42 strata | T+35 |
| 3 | `strata.py` | Raw records → stratum prices (min and median) | T+55 |
| 4 | `weights.py` | Three weight tables, loaded from config, validated to sum to 1 | T+70 |
| 5 | `index.py` | Base period + the §1.9 formula + sub-indices | T+90 |
| 6 | `clean.py` | Imputation + winsorizing, inserted *before* `index.py` in the pipeline | T+115 |
| 7 | `api.py` | `/index`, `/index/route/{r}`, `/index/horizon-band/{b}`, `/strata`, `/anomalies` | T+130 |

Two notes on this ordering.

**`seed.py` is the highest-leverage 20 minutes of the build.** It gives P3 realistic data to build charts against immediately, and it gives P2 a full panel to test the index formula against long before the scraper works. Generate fares with realistic structure: a base level per route, a rising curve as horizon shrinks, a weekend premium, and mild daily noise.

**`seed.py` is also not throwaway.** Keep it and present it as the **backfill module**. The justification is real: live scraping can only collect forward from today, but MoSPI needs historical context, so the synthetic backcast is calibrated against DGCA's published average fare series. This turns the prototype's biggest structural weakness into a deliberate design feature.

**`clean.py` sits at position 6 on purpose.** Get a working index first, then make it robust. An index without imputation still demos fine; a half-written imputation layer blocking the index does not.

### 2.4 Timeline

**T+15 → T+60 — Parallel build**

- **P1:** get one platform returning real fares. Timebox hard to 45 minutes. Ixigo and EaseMyTrip search endpoints are generally more forgiving than airline sites. If nothing works by T+60, commit the adapter interface with a stub implementation, move to supporting the pipeline, and let P4 adjust the narrative. A partially-working scraper honestly framed beats a demo that crashes.
- **P2:** modules 1–3.
- **P3:** dashboard shell built entirely against seeded data. Do not wait for the scraper.
- **P4:** rewrite the methodology slide around §1.9. This slide is the deck's centrepiece.
- **P5:** repo hygiene, environment setup, get a deployment target ready.

**T+60 → T+110 — First integration**

- Wire scraper → store → index → API → dashboard. **Something end-to-end must render by T+110, however ugly.**
- P2 completes modules 4–5.
- P4 takes the first screenshots.
- P5 sources real DGCA route and airline weights and replaces the placeholders.

**T+110 → T+150 — Depth**

- P2: `clean.py`, then sub-indices, then the weight sensitivity comparison.
- P5: cheap and honest ML — z-score anomaly flagging (already half-built inside `clean.py`), a 7-day linear or ARIMA index forecast. Label these as baseline models. Do not oversell.
- P3: anomaly panel, advance-purchase spread chart, provenance markers on imputed points.
- P4: architecture diagram matching what was actually built, not what was proposed.

**T+150 — Hard freeze. Non-negotiable.**

- **Record a screen capture of the complete working demo.** If the laptop dies, the venue wifi drops, or the scraper gets rate-limited during judging, the video plays. Teams lose on exactly this every year.
- No new features after this point. Bug fixes only.

**T+150 → T+180 — Rehearse**

- Full pitch, out loud, three times, timed.
- Assign who answers which category of question. Nobody improvises on methodology except P2.

### 2.5 Anticipated judge questions

| Question | Answer |
|---|---|
| Is scraping legal? | §1.14 — public fare display, robots.txt respected, rate-limited, no PII, no booking automation, aggregates only, and formal data-sharing replaces scraping in production. |
| How do you handle dynamic pricing volatility? | Fixed daily collection time, fixed days-to-departure buckets, geometric aggregation resists outliers, winsorizing at 3σ. |
| Why not just get data from airlines or DGCA? | DGCA reporting lags by months and covers traffic, not fares. In production MoSPI would negotiate direct feeds — APIx is the methodology and the pipeline, which remain identical either way. |
| Why a geometric mean? | Fare distributions are right-skewed with extreme values; Jevons is what ONS and Eurostat use for web-collected prices; it also has the correct time-reversal property. |
| Where do the weights come from? | Routes and airlines from DGCA. Horizons from an assumed prior — and here is the sensitivity analysis showing the index is robust to it. |
| Only three routes? | The slice is narrow by choice so that every weight is defensible. Widening it is a config change: add rows to the route table and the adapter loop. |
| What is actually AI/ML here? | Honest answer: anomaly detection and forecasting are baseline statistical models. The intellectual content is the index construction, not the ML. Say this plainly — judges reward it. |

### 2.6 Two things that will decide the result

**Be honest about collection coverage.** Say: "Our pipeline is source-agnostic. We have implemented and validated the adapter for Ixigo; the remaining platforms implement the same interface." Judges reward architectural honesty and punish demos that pretend to be more complete than they are.

**Make the methodology the centrepiece, not the dashboard.** Any team can scrape prices and plot them. Almost none will correctly explain elementary aggregates, geometric Laspeyres aggregation, base-period construction, weight sourcing, and CPI-standard imputation — mapped onto a statistics ministry's actual problem. That is the differentiator. Give P2's work the most slide time.

---

## Appendix — Outstanding items

- Team ID on the title slide still needs to be filled in manually.
- DGCA route and airline weights to be sourced and to replace the placeholder config values.
- Horizon weight prior to be explicitly labelled as an assumption on the methodology slide.
