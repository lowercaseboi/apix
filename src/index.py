"""Base period + the fixed-weight geometric Laspeyres formula + sub-indices
(PRD §1.9-1.12).

    APIx(t) = 100 * exp( sum_r w_r sum_d w_d sum_a w_a * ln(p[r,a,d](t) / p_bar[r,a,d](0)) )

compute_index() implements this as a single flattened weighted sum over the
42 (route, airline, horizon) strata rather than a literal 3D einsum, so it
can renormalize weights cleanly when an individual stratum is absent on a
given day (a single missing (r,a,d) cell isn't aligned to any one of the
three axes, so per-axis vector renormalization can't express it). When every
stratum is present, this is algebraically identical to
`np.einsum('r,d,a,rda->', w_r, w_d, w_a, log_rel)` from the PRD.

Sub-indices (route, airline, advance-purchase spread) reuse compute_index()
with a restricted or one-hot weight vector on one axis — no second
aggregation implementation, per CLAUDE.md.
"""

import numpy as np
import pandas as pd

from src.schema import AIRLINES, HORIZONS, ROUTES, STRATUM_KEYS
from src.weights import Weights, one_hot, restrict_and_renormalize

# Advance-purchase bands (PRD §1.12 names "<=7 day" and ">=30 day"; the PRD
# does not enumerate which of the 7 fixed horizons fall in each band, so
# this is an inference from the fixed horizon set {3,7,14,21,30,45,60}).
AP_SHORT_BAND = [3, 7]
AP_LONG_BAND = [30, 45, 60]


def compute_base_prices(panel: pd.DataFrame) -> dict:
    """Geometric mean of each stratum's first 7 distinct scrape days
    (PRD §1.9 Step B) — computed per stratum, before aggregation."""
    base_prices = {}
    for key, group in panel.groupby(["route", "airline", "horizon"]):
        first_7_days = sorted(group["scrape_day"].unique())[:7]
        first_7 = group[group["scrape_day"].isin(first_7_days)]
        base_prices[key] = float(np.exp(np.mean(np.log(first_7["min_fare"]))))
    return base_prices


def compute_index(
    panel: pd.DataFrame,
    base_prices: dict,
    w_route: dict,
    w_airline: dict,
    w_horizon: dict,
) -> pd.Series:
    full_weight = {
        key: w_route.get(key[0], 0.0) * w_airline.get(key[1], 0.0) * w_horizon.get(key[2], 0.0)
        for key in STRATUM_KEYS
    }

    results = {}
    for day, day_df in panel.groupby("scrape_day"):
        day_prices = day_df.set_index(["route", "airline", "horizon"])["min_fare"]

        weights_present = []
        log_rels = []
        for key, w in full_weight.items():
            if w == 0.0 or key not in day_prices.index:
                continue
            price = day_prices.loc[key]
            if isinstance(price, pd.Series):  # duplicate rows for the same stratum/day
                price = price.iloc[0]
            log_rels.append(np.log(price / base_prices[key]))
            weights_present.append(w)

        if not weights_present:
            continue

        weights_arr = np.array(weights_present)
        weights_arr = weights_arr / weights_arr.sum()  # renormalize to sum to 1
        results[day] = 100 * np.exp(np.dot(weights_arr, np.array(log_rels)))

    return pd.Series(results).sort_index()


def compute_route_index(panel, base_prices, weights: Weights, route: str) -> pd.Series:
    return compute_index(panel, base_prices, one_hot(ROUTES, route), weights.airline, weights.horizon)


def compute_airline_index(panel, base_prices, weights: Weights, airline: str) -> pd.Series:
    return compute_index(panel, base_prices, weights.route, one_hot(AIRLINES, airline), weights.horizon)


def compute_ap_spread_indices(panel, base_prices, weights: Weights) -> tuple[pd.Series, pd.Series]:
    w_short = restrict_and_renormalize(weights.horizon, AP_SHORT_BAND)
    w_long = restrict_and_renormalize(weights.horizon, AP_LONG_BAND)
    short_index = compute_index(panel, base_prices, weights.route, weights.airline, w_short)
    long_index = compute_index(panel, base_prices, weights.route, weights.airline, w_long)
    return short_index, long_index


if __name__ == "__main__":
    from src.clean import clean_panel
    from src.strata import load_panel, reduce_to_strata
    from src.weights import load_weights

    weights = load_weights()
    reduced = clean_panel(reduce_to_strata(load_panel()))
    base_prices = compute_base_prices(reduced)

    headline = compute_index(reduced, base_prices, weights.route, weights.airline, weights.horizon)
    print("Headline APIx — first 7 days (base period):")
    print(headline.head(7).to_string())
    print("\nHeadline APIx — last 5 days:")
    print(headline.tail(5).to_string())

    route_idx = compute_route_index(reduced, base_prices, weights, "DEL-BOM")
    print("\nDEL-BOM route index — last 5 days:")
    print(route_idx.tail(5).to_string())

    short_idx, long_idx = compute_ap_spread_indices(reduced, base_prices, weights)
    print("\nAP spread (<=7 day vs >=30 day) — last 5 days:")
    print(pd.DataFrame({"short_ap": short_idx, "long_ap": long_idx}).tail(5).to_string())
