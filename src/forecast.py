"""7-day baseline forecast of the headline index.

Ordinary least squares on a linear trend PLUS day-of-week effects. It is a
baseline statistical model — not machine learning, and not "AI-powered"
(CLAUDE.md honesty rules).

Why day-of-week matters: fares carry a weekend departure premium, and
because each stratum holds days-to-departure constant, that premium cycles
weekly through the index. On the current panel the gap between the
strongest and weakest weekday is ~6.5 index points, while the underlying
trend is ~0.01 points/day. A trend-only line is therefore structurally
blind to almost all of the movement it claims to predict — measured
against a hold-out it scored no better than assuming nothing changes.

Every forecast is reported with backtest_ratio: its hold-out error divided
by that of the naive "assume no change" rule. Below 1.0 means the model
beat doing nothing; at or above 1.0 it did not, and should not be shown.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

METHOD_LABEL = "OLS trend + day-of-week effects (baseline model)"
DEFAULT_WINDOW_DAYS = 56  # 8 whole weeks, so every weekday is equally represented
DEFAULT_FORECAST_DAYS = 7


def _design_matrix(dates, n) -> np.ndarray:
    """Intercept, linear trend, and six day-of-week dummies (Monday is the
    reference level, so its effect is folded into the intercept)."""
    t = np.arange(n, dtype=float)
    dow = np.array([d.weekday() for d in dates])
    cols = [np.ones(n), t]
    for k in range(1, 7):
        cols.append((dow == k).astype(float))
    return np.column_stack(cols)


def _fit(series: pd.Series):
    n = len(series)
    dates = [pd.Timestamp(d).to_pydatetime() for d in series.index]
    X = _design_matrix(dates, n)
    y = series.to_numpy(dtype=float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ coef
    return coef, residuals


def _predict(coef, start_index: int, future_dates) -> np.ndarray:
    n = len(future_dates)
    t = np.arange(start_index, start_index + n, dtype=float)
    dow = np.array([d.weekday() for d in future_dates])
    cols = [np.ones(n), t]
    for k in range(1, 7):
        cols.append((dow == k).astype(float))
    return np.column_stack(cols) @ coef


def backtest(series: pd.Series, days: int = DEFAULT_FORECAST_DAYS,
             window: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Hold out the last `days`, fit on the rest, and compare against two
    naive rules. Reported so the forecast's value is checkable rather than
    asserted."""
    if len(series) < window + days + 7:
        return {}

    train, actual = series.iloc[:-days], series.iloc[-days:]
    recent = train.tail(window)
    coef, _ = _fit(recent)
    future = [pd.Timestamp(d).to_pydatetime() for d in actual.index]
    pred = _predict(coef, len(recent), future)

    y = actual.to_numpy(dtype=float)
    mae = lambda a: float(np.abs(a - y).mean())
    model_mae = mae(pred)
    naive_mae = mae(np.repeat(train.to_numpy()[-1], days))

    return {
        "model_mae": model_mae,
        "naive_no_change_mae": naive_mae,
        "seasonal_naive_mae": mae(train.to_numpy()[-days:]),
        "backtest_ratio": model_mae / naive_mae if naive_mae else float("nan"),
        "holdout_days": days,
    }


def linear_baseline_forecast(series: pd.Series, days: int = DEFAULT_FORECAST_DAYS,
                             window: int = DEFAULT_WINDOW_DAYS) -> dict:
    recent = series.tail(window)
    coef, residuals = _fit(recent)

    last_day = pd.Timestamp(recent.index[-1]).to_pydatetime()
    future_dates = [last_day + timedelta(days=s) for s in range(1, days + 1)]
    values = _predict(coef, len(recent), future_dates)

    dof = max(1, len(recent) - len(coef))
    residual_std = float(np.sqrt((residuals**2).sum() / dof))

    weekday_effects = {
        name: float(v)
        for name, v in zip(
            ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], coef[2:]
        )
    }

    return {
        "method": METHOD_LABEL,
        "window_days": len(recent),
        "forecast_days": days,
        "slope_per_day": float(coef[1]),
        "weekday_effects_vs_monday": weekday_effects,
        "residual_std": residual_std,
        "residual_std_note": "In-sample residual standard deviation, not a forecast interval.",
        "projection": [
            {"date": d.date().isoformat(), "value": float(v)}
            for d, v in zip(future_dates, values)
        ],
        "backtest": backtest(series, days=days, window=window),
    }


if __name__ == "__main__":
    from src.clean import clean_panel
    from src.index import compute_base_prices, compute_index
    from src.strata import load_panel, reduce_to_strata
    from src.weights import load_weights

    weights = load_weights()
    panel = clean_panel(reduce_to_strata(load_panel()))
    base_prices = compute_base_prices(panel)
    headline = compute_index(panel, base_prices, weights.route, weights.airline, weights.horizon)
    headline.index = pd.to_datetime(list(headline.index))

    r = linear_baseline_forecast(headline)
    print(f"{r['method']}, fitted over {r['window_days']} days")
    print(f"  trend           : {r['slope_per_day']:+.4f} index points/day")
    print(f"  residual sigma  : {r['residual_std']:.3f} (not a forecast interval)")
    print("\n  day-of-week effects vs Monday:")
    for k, v in r["weekday_effects_vs_monday"].items():
        print(f"    {k}: {v:+6.2f}")
    bt = r["backtest"]
    if bt:
        print(f"\n  backtest on a {bt['holdout_days']}-day hold-out:")
        print(f"    this model        MAE {bt['model_mae']:.3f}")
        print(f"    assume no change  MAE {bt['naive_no_change_mae']:.3f}")
        print(f"    same day last wk  MAE {bt['seasonal_naive_mae']:.3f}")
        print(f"    ratio vs naive    {bt['backtest_ratio']:.2f}  "
              f"({'beats' if bt['backtest_ratio'] < 1 else 'DOES NOT BEAT'} doing nothing)")
    print("\n  projection:")
    for p in r["projection"]:
        print(f"    {p['date']}  {p['value']:.3f}")
