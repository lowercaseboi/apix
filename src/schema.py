"""FareRecord: the frozen contract every pipeline module codes against.

Changing this file means coordinating with the other three people on the
team (see CLAUDE.md). Do not add fields or change semantics casually.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class FareRecord:
    route: str            # "DEL-BOM"
    airline: str           # "6E" | "SG"
    dep_date: date
    scrape_ts: datetime    # UTC
    horizon: int           # 3|7|14|21|30|45|60
    flight_no: str
    fare_inr: float        # base fare + statutory taxes, no add-ons
    fare_class: str        # "economy"
    source: str            # "ixigo" | "easemytrip" | "synthetic" (seed/backfill)
    is_imputed: bool = False
    is_winsorized: bool = False


# Fixed scope (frozen decisions in CLAUDE.md) — 3 routes x 2 airlines x 7 horizons.
ROUTES = ["DEL-BOM", "DEL-BLR", "BOM-BLR"]
AIRLINES = ["6E", "SG"]
HORIZONS = [3, 7, 14, 21, 30, 45, 60]

StratumKey = tuple[str, str, int]  # (route, airline, horizon)

STRATUM_KEYS: list[StratumKey] = [
    (route, airline, horizon)
    for route in ROUTES
    for airline in AIRLINES
    for horizon in HORIZONS
]  # 3 x 2 x 7 = 42


def stratum_key(record: FareRecord) -> StratumKey:
    return (record.route, record.airline, record.horizon)
