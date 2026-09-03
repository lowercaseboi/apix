"""Weight sensitivity check (PRD §1.11).

The PRD prescribes exactly one check: "recompute the index with uniform
horizon weights and show that the series barely moves." Horizon weights are
the only assumed prior among the three vectors, so they are the only ones
perturbed here — route and airline weights are sourced (or placeholder)
figures, not assumptions the index rests on.

Two extra tilts (front-loaded, back-loaded) are included as illustrative
bounds. They are NOT part of the PRD's prescribed check and are labelled as
such wherever they surface.

Every scenario goes through index.compute_index — no second aggregation
implementation.
"""

import numpy as np

from src.index import compute_index
from src.schema import HORIZONS
from src.weights import Weights

# Illustrative extremes, not PRD-prescribed. Normalised on construction.
_FRONT_LOADED = {3: 0.35, 7: 0.25, 14: 0.15, 21: 0.10, 30: 0.08, 45: 0.04, 60: 0.03}
_BACK_LOADED = {3: 0.03, 7: 0.04, 14: 0.08, 21: 0.10, 30: 0.15, 45: 0.25, 60: 0.35}


def _normalised(weights: dict[int, float]) -> dict[int, float]:
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def uniform_horizon_weights() -> dict[int, float]:
    return {h: 1.0 / len(HORIZONS) for h in HORIZONS}


def horizon_weight_scenarios(weights: Weights) -> dict[str, dict[int, float]]:
    return {
        "config": weights.horizon,
        "uniform": uniform_horizon_weights(),
        "front_loaded": _normalised(_FRONT_LOADED),
        "back_loaded": _normalised(_BACK_LOADED),
    }


def compare_horizon_weight_scenarios(panel, base_prices, weights: Weights) -> dict:
    scenarios = horizon_weight_scenarios(weights)
    series = {
        name: compute_index(panel, base_prices, weights.route, weights.airline, w_horizon)
        for name, w_horizon in scenarios.items()
    }

    headline = series["config"]
    deviations = {
        name: float(np.abs(s - headline).max())
        for name, s in series.items()
        if name != "config"
    }

    return {
        "series": series,
        "max_abs_deviation": deviations,
        "prescribed_scenario": "uniform",
    }


if __name__ == "__main__":
    from src.clean import clean_panel
    from src.index import compute_base_prices
    from src.strata import load_panel, reduce_to_strata
    from src.weights import load_weights

    weights = load_weights()
    panel = clean_panel(reduce_to_strata(load_panel()))
    base_prices = compute_base_prices(panel)

    result = compare_horizon_weight_scenarios(panel, base_prices, weights)

    print("Max absolute deviation from the headline index (index points):")
    for name, dev in result["max_abs_deviation"].items():
        tag = "  <- PRD-prescribed check" if name == result["prescribed_scenario"] else ""
        print(f"  {name:<14} {dev:.3f}{tag}")

    print("\nLast 5 days, all scenarios:")
    import pandas as pd

    print(pd.DataFrame(result["series"]).tail(5).to_string())
