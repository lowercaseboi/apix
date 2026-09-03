"""Collapse raw FareRecords into one price per stratum per day.

Primary rule: minimum fare across all flights in a (route, airline, horizon)
stratum on a given day — this is the consumer-relevant price that feeds
clean.py and index.py downstream.

Secondary rule: median fare across the same set, computed in parallel as a
robustness variant. It is exposed on the dashboard as a toggle but never
feeds the index calculation itself.

No imputation or winsorizing happens here — that is clean.py's job. This
module only reduces raw flights to (min, median) pairs per stratum per day.
"""

from pathlib import Path

import pandas as pd

from src.schema import AIRLINES, HORIZONS, ROUTES
from src.seed import OUTPUT_PATH


def load_panel(path: Path = OUTPUT_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


def reduce_to_strata(panel: pd.DataFrame) -> pd.DataFrame:
    """Reduce a raw fare panel to one (min_fare, median_fare) row per
    (dep_date-derived scrape day via scrape_ts, route, airline, horizon).

    Grouping key uses scrape_ts's date (the day the price was observed),
    since horizon + scrape day together fix dep_date for a given stratum.
    """
    df = panel.copy()
    df["scrape_day"] = pd.to_datetime(df["scrape_ts"]).dt.date

    grouped = (
        df.groupby(["scrape_day", "route", "airline", "horizon"])["fare_inr"]
        .agg(min_fare="min", median_fare="median")
        .reset_index()
    )
    return grouped


def strata_for_day(reduced: pd.DataFrame, scrape_day) -> pd.DataFrame:
    """Return the (up to) 42 stratum rows for a single scrape day, sorted
    for readability."""
    day_rows = reduced[reduced["scrape_day"] == scrape_day]
    return day_rows.sort_values(["route", "airline", "horizon"]).reset_index(drop=True)


if __name__ == "__main__":
    panel = load_panel()
    reduced = reduce_to_strata(panel)

    sample_day = sorted(reduced["scrape_day"].unique())[-1]
    sample = strata_for_day(reduced, sample_day)

    expected_strata = len(ROUTES) * len(AIRLINES) * len(HORIZONS)
    print(f"Sample scrape day: {sample_day}")
    print(f"Strata present: {len(sample)} (expected {expected_strata})")
    print(f"min_fare <= median_fare for all rows: {(sample['min_fare'] <= sample['median_fare']).all()}")
    print(sample.to_string(index=False))
