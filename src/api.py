"""FastAPI app: /index, /index/route/{r}, /index/airline/{a},
/index/horizon-band/{b}, /strata, /anomalies (PRD §2.3/FR-6/FR-7), plus
/sources, /sensitivity and /forecast.

Four of these go beyond CLAUDE.md's literally-listed routes:
/index/airline/{a} (FR-7 requires an airline comparison view), /sensitivity
(PRD §1.11's prescribed weight check), /forecast (a §1.13 "could have"),
and /sources (the §2.6 collection-honesty story, on screen). Response
shapes, the /index/horizon-band/{b} slug names ("le7"/"ge30"), and CORS are
all design choices — the PRD is silent on all three.

Data is loaded and cleaned once at import time (module-level), not per
request: the panel is static synthetic data for now, so there's nothing to
gain from recomputing on every call.
"""

import json

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.adapters import REGISTRY
from src.clean import clean_panel
from src.collect import STATUS_PATH
from src.forecast import linear_baseline_forecast
from src.index import (
    compute_airline_index,
    compute_ap_spread_indices,
    compute_base_prices,
    compute_index,
    compute_route_index,
)
from src.schema import AIRLINES, ROUTES
from src.sensitivity import compare_horizon_weight_scenarios
from src.strata import load_panel, reduce_to_strata
from src.weights import load_weights

app = FastAPI(title="APIx")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_panel = clean_panel(reduce_to_strata(load_panel()))
_base_prices = compute_base_prices(_panel)
_weights = load_weights()

AP_BANDS = {"le7": 0, "ge30": 1}  # index into compute_ap_spread_indices()'s (short, long) tuple


def _series_to_json(series: pd.Series) -> list[dict]:
    return [
        {"date": day.isoformat() if hasattr(day, "isoformat") else str(day), "value": value}
        for day, value in series.items()
    ]


@app.get("/index")
def get_index():
    series = compute_index(_panel, _base_prices, _weights.route, _weights.airline, _weights.horizon)
    return _series_to_json(series)


@app.get("/index/route/{r}")
def get_route_index(r: str):
    if r not in ROUTES:
        raise HTTPException(status_code=404, detail=f"Unknown route {r!r}. Valid routes: {ROUTES}")
    series = compute_route_index(_panel, _base_prices, _weights, r)
    return _series_to_json(series)


@app.get("/index/airline/{a}")
def get_airline_index(a: str):
    # Not one of CLAUDE.md's literally-listed api.py routes, but FR-7
    # requires an airline comparison view and no existing endpoint can
    # serve it without duplicating index math client-side.
    if a not in AIRLINES:
        raise HTTPException(status_code=404, detail=f"Unknown airline {a!r}. Valid airlines: {AIRLINES}")
    series = compute_airline_index(_panel, _base_prices, _weights, a)
    return _series_to_json(series)


@app.get("/index/horizon-band/{b}")
def get_horizon_band_index(b: str):
    if b not in AP_BANDS:
        raise HTTPException(
            status_code=404, detail=f"Unknown horizon band {b!r}. Valid bands: {list(AP_BANDS)}"
        )
    short_index, long_index = compute_ap_spread_indices(_panel, _base_prices, _weights)
    series = short_index if b == "le7" else long_index
    return _series_to_json(series)


@app.get("/strata")
def get_strata():
    df = _panel.copy()
    df["scrape_day"] = df["scrape_day"].astype(str)
    return df.where(df.notna(), None).to_dict(orient="records")


@app.get("/anomalies")
def get_anomalies():
    # Anomaly flagging is a fixed 3-sigma threshold on each stratum's own
    # day-over-day log-relative distribution (clean.py) — a baseline
    # statistical rule, not "AI-powered", per CLAUDE.md's honesty rules.
    flagged = _panel[_panel["is_winsorized"]].copy()
    flagged["scrape_day"] = flagged["scrape_day"].astype(str)
    records = flagged[
        ["scrape_day", "route", "airline", "horizon", "min_fare_raw", "min_fare"]
    ].rename(columns={"min_fare_raw": "raw_fare_inr", "min_fare": "adjusted_fare_inr"})
    return records.to_dict(orient="records")


@app.get("/sources")
def get_sources():
    # Reads the status written by `python -m src.collect` rather than
    # hitting each platform per request: repeated robots.txt fetches on
    # every page load would be impolite, and it keeps the demo working
    # offline.
    if not STATUS_PATH.exists():
        return {
            "cycle_run_at": None,
            "sources": [
                {"source": name, "robots_allowed": None, "reason": "not checked yet"}
                for name in REGISTRY
            ],
            "total_records_collected": 0,
            "note": "No collection cycle has been run. Run `python -m src.collect`.",
        }
    return json.loads(STATUS_PATH.read_text())


@app.get("/sensitivity")
def get_sensitivity():
    result = compare_horizon_weight_scenarios(_panel, _base_prices, _weights)
    return {
        "prescribed_scenario": result["prescribed_scenario"],
        "max_abs_deviation": result["max_abs_deviation"],
        "series": {name: _series_to_json(s) for name, s in result["series"].items()},
        "note": (
            "Only horizon weights are perturbed — they are the one assumed prior "
            "in the index (PRD §1.11). 'uniform' is the prescribed check; "
            "'front_loaded' and 'back_loaded' are illustrative extremes."
        ),
    }


@app.get("/forecast")
def get_forecast():
    headline = compute_index(_panel, _base_prices, _weights.route, _weights.airline, _weights.horizon)
    result = linear_baseline_forecast(headline)
    result["recent"] = _series_to_json(headline.tail(30))
    return result
