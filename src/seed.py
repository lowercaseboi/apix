"""Synthetic fare panel generator — also serves as the backfill module.

Storage choice: a single Parquet file (data/seed_panel.parquet). Parquet is
columnar, preserves date/datetime dtypes exactly on reload, and needs no
schema setup (unlike SQLite) for a simple generate-once/read-many panel.
strata.py loads it with a single pd.read_parquet call.

All records produced here carry source="synthetic" so they are visibly
distinguishable from live-scraped data at every downstream layer, per
CLAUDE.md's honesty rules for backfill data.

Price model (NONE of these numbers come from the PRD — it only specifies
the qualitative shape: "a base level per route, a rising curve as horizon
shrinks, a weekend premium, and mild daily noise". The concrete constants
below are implementation placeholders and should be revisited by the team):
  - BASE_FARE_INR: a distinct flat base per route.
  - Horizon curve: fare rises as horizon shrinks, modeled as
    base * (1 + HORIZON_CURVE_K / horizon) — an assumed inverse relationship,
    not measured data.
  - Weekend premium: +WEEKEND_PREMIUM if dep_date falls on Sat/Sun.
  - Daily noise: multiplicative Gaussian noise, stdev NOISE_STD, drawn from
    a single seeded RNG (numpy.random.default_rng) so runs are reproducible.
"""

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.schema import AIRLINES, HORIZONS, ROUTES, FareRecord

# --- Placeholder price-model constants (see module docstring) ---
BASE_FARE_INR = {
    "DEL-BOM": 4500.0,
    "DEL-BLR": 5200.0,
    "BOM-BLR": 3800.0,
}
AIRLINE_MULTIPLIER = {"6E": 1.00, "SG": 0.95}  # SG priced slightly below 6E, assumed
HORIZON_CURVE_K = 2.5       # bigger => steeper last-minute rise
WEEKEND_PREMIUM = 0.12      # +12% on Sat/Sun departures, assumed
NOISE_STD = 0.03            # 3% daily multiplicative noise, assumed
FLIGHT_NUMBERS_PER_STRATUM = 3  # distinct flights/day so min != median is meaningful

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "seed_panel.parquet"


def _fare_for(
    rng: np.random.Generator,
    route: str,
    airline: str,
    horizon: int,
    dep_date: date,
) -> float:
    base = BASE_FARE_INR[route] * AIRLINE_MULTIPLIER[airline]
    horizon_factor = 1 + HORIZON_CURVE_K / horizon
    weekend_factor = 1 + WEEKEND_PREMIUM if dep_date.weekday() >= 5 else 1.0
    noise_factor = 1 + rng.normal(0, NOISE_STD)
    return round(base * horizon_factor * weekend_factor * noise_factor, 2)


def generate_panel(days: int, seed: int) -> list[FareRecord]:
    rng = np.random.default_rng(seed)
    today = datetime.now(timezone.utc).date()
    records: list[FareRecord] = []

    for day_offset in range(days):
        scrape_day = today - timedelta(days=days - 1 - day_offset)
        scrape_ts = datetime(
            scrape_day.year, scrape_day.month, scrape_day.day, tzinfo=timezone.utc
        )
        for route in ROUTES:
            for airline in AIRLINES:
                for horizon in HORIZONS:
                    dep_date = scrape_day + timedelta(days=horizon)
                    for flight_idx in range(FLIGHT_NUMBERS_PER_STRATUM):
                        fare = _fare_for(rng, route, airline, horizon, dep_date)
                        records.append(
                            FareRecord(
                                route=route,
                                airline=airline,
                                dep_date=dep_date,
                                scrape_ts=scrape_ts,
                                horizon=horizon,
                                flight_no=f"{airline}{100 + flight_idx}",
                                fare_inr=fare,
                                fare_class="economy",
                                source="synthetic",
                                is_imputed=False,
                                is_winsorized=False,
                            )
                        )
    return records


def write_panel(records: list[FareRecord], output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([r.__dict__ for r in records])
    df.to_parquet(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic APIx fare panel.")
    parser.add_argument("--days", type=int, default=90, help="Number of scrape days to generate.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    args = parser.parse_args()

    records = generate_panel(args.days, args.seed)
    write_panel(records)
    print(
        f"Wrote {len(records)} FareRecords "
        f"({args.days} days x 42 strata x {FLIGHT_NUMBERS_PER_STRATUM} flights) "
        f"to {OUTPUT_PATH} (seed={args.seed})"
    )


if __name__ == "__main__":
    main()
