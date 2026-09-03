"""Imputation + winsorizing (PRD §1.10). Runs BEFORE index.py in the fixed
pipeline (adapters -> strata -> clean -> index).

Two PRD-specified rules, both operating on min_fare (the index-feeding
primary series — see the "median_fare treatment" note below):

  - Missing stratum-days: gaps <= MAX_IMPUTE_GAP_DAYS are imputed using the
    average day-over-day log-relative of sibling strata (same route+airline,
    other horizons). Gaps longer than that are left absent — index.py's
    compute_index() already renormalizes over whatever strata are present
    each day, which is exactly the "drop + renormalize" behavior the PRD
    calls for.
  - Outliers: any day where |log-relative day-over-day change| > 3 sigma of
    that stratum's own historical Delta distribution is winsorized (clipped
    to the 3-sigma bound), never dropped.

Assumptions the PRD leaves unspecified (see plan/report for detail):
  - Sibling strata for imputation are the same route AND airline, other
    horizons only (not other airlines) — the fixed-scope route x airline
    pairing is the comparable "product."
  - Winsorizing requires at least MIN_SIGMA_SAMPLE historical day-over-day
    deltas before it activates for a stratum (the PRD gives no window or
    minimum-N; a sigma computed off a handful of points is unstable).
  - Imputation runs before winsorizing, so the outlier check sees a
    structurally-complete series (PRD states no ordering).
  - median_fare has no independently observed value for an imputed
    stratum-day, so it is left NaN there; only min_fare is ever winsorized
    (median_fare passes through unchanged for real, observed rows).
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.schema import STRATUM_KEYS

MAX_IMPUTE_GAP_DAYS = 3
WINSOR_SIGMA = 3.0
MIN_SIGMA_SAMPLE = 10  # minimum historical deltas before winsorizing activates


def _consecutive_runs(days: list[date]) -> list[list[date]]:
    """Group a sorted list of dates into consecutive-day runs."""
    if not days:
        return []
    runs = [[days[0]]]
    for day in days[1:]:
        if day - runs[-1][-1] == timedelta(days=1):
            runs[-1].append(day)
        else:
            runs.append([day])
    return runs


def impute_gaps(reduced_df: pd.DataFrame) -> pd.DataFrame:
    df = reduced_df.copy()
    df["is_imputed"] = False
    all_days = sorted(df["scrape_day"].unique())

    by_stratum = {
        key: g.set_index("scrape_day")["min_fare"].to_dict()
        for key, g in df.groupby(["route", "airline", "horizon"])
    }

    imputed_rows = []
    for route, airline, horizon in STRATUM_KEYS:
        present = by_stratum.get((route, airline, horizon), {})
        missing_days = [d for d in all_days if d not in present]
        for run in _consecutive_runs(missing_days):
            if len(run) > MAX_IMPUTE_GAP_DAYS:
                continue  # dropped: renormalization in index.py handles this

            for day in run:
                day_index = all_days.index(day)
                if day_index == 0:
                    continue  # no prior day to impute from
                prev_day = all_days[day_index - 1]
                prev_price = present.get(prev_day)
                if prev_price is None:
                    continue  # prior day itself unavailable; can't propagate

                sibling_deltas = []
                for sib_route, sib_airline, sib_horizon in STRATUM_KEYS:
                    if (sib_route, sib_airline) != (route, airline) or sib_horizon == horizon:
                        continue
                    sib_prices = by_stratum.get((sib_route, sib_airline, sib_horizon), {})
                    if day in sib_prices and prev_day in sib_prices:
                        sibling_deltas.append(np.log(sib_prices[day] / sib_prices[prev_day]))

                mean_sibling_delta = np.mean(sibling_deltas) if sibling_deltas else 0.0
                imputed_price = prev_price * np.exp(mean_sibling_delta)

                present[day] = imputed_price  # so later days in the run can propagate
                imputed_rows.append(
                    {
                        "scrape_day": day,
                        "route": route,
                        "airline": airline,
                        "horizon": horizon,
                        "min_fare": imputed_price,
                        "median_fare": np.nan,
                        "is_imputed": True,
                    }
                )

    if imputed_rows:
        df = pd.concat([df, pd.DataFrame(imputed_rows)], ignore_index=True)
    return df


def winsorize_outliers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_winsorized"] = False
    df["min_fare_raw"] = df["min_fare"]

    updated_frames = []
    for key, group in df.groupby(["route", "airline", "horizon"]):
        group = group.sort_values("scrape_day").reset_index(drop=True)
        raw_prices = group["min_fare"].to_numpy()

        if len(raw_prices) < MIN_SIGMA_SAMPLE + 1:
            updated_frames.append(group)
            continue

        raw_deltas = np.diff(np.log(raw_prices))
        sigma = raw_deltas.std(ddof=0)

        adjusted = raw_prices.copy()
        for i in range(1, len(adjusted)):
            delta = np.log(raw_prices[i]) - np.log(adjusted[i - 1])
            if sigma > 0 and abs(delta) > WINSOR_SIGMA * sigma:
                clipped_delta = np.sign(delta) * WINSOR_SIGMA * sigma
                adjusted[i] = adjusted[i - 1] * np.exp(clipped_delta)
                group.loc[i, "is_winsorized"] = True
            else:
                adjusted[i] = adjusted[i - 1] * np.exp(delta)

        group["min_fare"] = adjusted
        updated_frames.append(group)

    return pd.concat(updated_frames, ignore_index=True)


def clean_panel(reduced_df: pd.DataFrame) -> pd.DataFrame:
    return winsorize_outliers(impute_gaps(reduced_df))


if __name__ == "__main__":
    from src.strata import load_panel, reduce_to_strata

    reduced = reduce_to_strata(load_panel())

    # Perturb a copy of the real reduced panel to demonstrate the two rules
    # on realistic-shaped data (the actual seed panel has no gaps/outliers).
    demo = reduced.copy()
    days = sorted(demo["scrape_day"].unique())

    gap_stratum = STRATUM_KEYS[0]  # <=3-day gap: should be imputed
    drop_stratum = STRATUM_KEYS[1]  # >3-day gap: should stay absent
    spike_stratum = STRATUM_KEYS[2]  # single-day price spike: should be winsorized

    gap_mask = (
        (demo["route"] == gap_stratum[0])
        & (demo["airline"] == gap_stratum[1])
        & (demo["horizon"] == gap_stratum[2])
        & (demo["scrape_day"].isin(days[10:12]))
    )
    drop_mask = (
        (demo["route"] == drop_stratum[0])
        & (demo["airline"] == drop_stratum[1])
        & (demo["horizon"] == drop_stratum[2])
        & (demo["scrape_day"].isin(days[20:26]))
    )
    demo = demo[~(gap_mask | drop_mask)].reset_index(drop=True)

    spike_mask = (
        (demo["route"] == spike_stratum[0])
        & (demo["airline"] == spike_stratum[1])
        & (demo["horizon"] == spike_stratum[2])
        & (demo["scrape_day"] == days[15])
    )
    demo.loc[spike_mask, "min_fare"] *= 5.0  # obvious outlier spike

    cleaned = clean_panel(demo)

    print(f"Gap stratum {gap_stratum} imputed rows (days {days[10]}..{days[11]}):")
    print(
        cleaned[
            (cleaned["route"] == gap_stratum[0])
            & (cleaned["airline"] == gap_stratum[1])
            & (cleaned["horizon"] == gap_stratum[2])
            & (cleaned["scrape_day"].isin(days[9:13]))
        ][["scrape_day", "min_fare", "is_imputed"]].to_string(index=False)
    )

    still_absent = cleaned[
        (cleaned["route"] == drop_stratum[0])
        & (cleaned["airline"] == drop_stratum[1])
        & (cleaned["horizon"] == drop_stratum[2])
        & (cleaned["scrape_day"].isin(days[20:26]))
    ]
    print(f"\nDrop stratum {drop_stratum}: rows present for the >3-day gap window: {len(still_absent)} (expected 0)")

    spike_row = cleaned[
        (cleaned["route"] == spike_stratum[0])
        & (cleaned["airline"] == spike_stratum[1])
        & (cleaned["horizon"] == spike_stratum[2])
        & (cleaned["scrape_day"] == days[15])
    ]
    print(f"\nSpike stratum {spike_stratum} on {days[15]} — raw vs adjusted:")
    print(spike_row[["scrape_day", "min_fare_raw", "min_fare", "is_winsorized"]].to_string(index=False))
