import pandas as pd
import pytest

from src.index import compute_base_prices, compute_index
from src.schema import AIRLINES, HORIZONS, ROUTES, STRATUM_KEYS
from src.weights import load_weights

DAYS = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04",
        "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]


def _panel(fare_for_day):
    """Build a panel with one row per (day, stratum), fare given by
    fare_for_day(day_index) -> float, identical across all 42 strata."""
    rows = []
    for day_index, day in enumerate(DAYS):
        for route, airline, horizon in STRATUM_KEYS:
            rows.append(
                {
                    "scrape_day": day,
                    "route": route,
                    "airline": airline,
                    "horizon": horizon,
                    "min_fare": fare_for_day(day_index),
                    "median_fare": fare_for_day(day_index),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def weights():
    return load_weights()


def test_flat_panel_returns_100(weights):
    panel = _panel(lambda i: 5000.0)
    base_prices = compute_base_prices(panel)
    index = compute_index(panel, base_prices, weights.route, weights.airline, weights.horizon)

    assert (index.round(9) == 100.0).all()


def test_uniform_10_percent_rise_returns_110(weights):
    # First 7 days form the base period at 5000; day 8 rises 10% everywhere.
    panel = _panel(lambda i: 5000.0 if i < 7 else 5500.0)
    base_prices = compute_base_prices(panel)
    index = compute_index(panel, base_prices, weights.route, weights.airline, weights.horizon)

    assert index.iloc[-1] == pytest.approx(110.0)


def test_weights_not_summing_to_one_raises(tmp_path):
    bad_yaml = tmp_path / "bad_weights.yaml"
    bad_yaml.write_text(
        "horizon: {3: 0.5, 7: 0.6}\nroute: {DEL-BOM: 1.0}\nairline: {6E: 1.0}\n"
    )
    with pytest.raises(ValueError):
        load_weights(bad_yaml)


def test_removing_a_stratum_renormalizes_and_does_not_shift_index(weights):
    panel = _panel(lambda i: 5000.0 if i < 7 else 5500.0)
    base_prices = compute_base_prices(panel)

    full_index = compute_index(panel, base_prices, weights.route, weights.airline, weights.horizon)

    dropped_key = STRATUM_KEYS[0]
    dropped_route, dropped_airline, dropped_horizon = dropped_key
    reduced_panel = panel[
        ~(
            (panel["route"] == dropped_route)
            & (panel["airline"] == dropped_airline)
            & (panel["horizon"] == dropped_horizon)
        )
    ]
    reduced_base_prices = {k: v for k, v in base_prices.items() if k != dropped_key}

    reduced_index = compute_index(
        reduced_panel, reduced_base_prices, weights.route, weights.airline, weights.horizon
    )

    assert reduced_index.iloc[-1] == pytest.approx(110.0)
    assert full_index.iloc[-1] == pytest.approx(reduced_index.iloc[-1])
