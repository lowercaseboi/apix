"""One collection cycle: `python -m src.collect`.

Queries fixed horizons, not date windows — every run asks each platform for
departures at exactly D = {3,7,14,21,30,45,60} days ahead (frozen decision
in CLAUDE.md), which keeps the panel balanced by construction.

Compliance comes first. Each source's robots.txt is checked once per cycle;
a disallowed source is skipped entirely and contributes zero records. A
blocked platform reduces coverage and is reported as such — it never
crashes the pipeline and is never backfilled with fabricated data (PRD §1.7
graceful degradation, §1.14 legal position).

Output goes under data/, which is gitignored: raw fare tables are never
committed or exposed, only derived aggregates are published.
"""

import json
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.adapters import REGISTRY, RobotsDisallowed, get_source
from src.schema import HORIZONS, ROUTES, FareRecord

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COLLECTED_PATH = DATA_DIR / "collected_panel.parquet"
STATUS_PATH = DATA_DIR / "collection_status.json"


def run_cycle(today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    statuses = []
    records: list[FareRecord] = []

    for name in REGISTRY:
        source = get_source(name)
        status = source.check_compliance()
        collected_here = 0
        errors: list[str] = []

        if status.robots_allowed:
            for route in ROUTES:
                for horizon in HORIZONS:
                    dep_date = today + timedelta(days=horizon)
                    try:
                        fetched = source.fetch(route, dep_date, horizon)
                    except (RobotsDisallowed, NotImplementedError) as exc:
                        errors.append(f"{route}@{horizon}d: {exc}")
                        continue
                    records.extend(fetched)
                    collected_here += len(fetched)

        entry = status.as_dict()
        entry["records_collected"] = collected_here
        entry["queries_attempted"] = len(ROUTES) * len(HORIZONS) if status.robots_allowed else 0
        entry["errors"] = errors[:5]
        statuses.append(entry)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "cycle_run_at": datetime.now(timezone.utc).isoformat(),
        "collection_date": today.isoformat(),
        "sources": statuses,
        "total_records_collected": len(records),
    }
    STATUS_PATH.write_text(json.dumps(summary, indent=2))

    if records:
        pd.DataFrame([asdict(r) for r in records]).to_parquet(COLLECTED_PATH, index=False)

    return summary


def main() -> None:
    summary = run_cycle()
    print(f"Collection cycle for {summary['collection_date']} (UTC)\n")
    for entry in summary["sources"]:
        verdict = "ALLOWED" if entry["robots_allowed"] else "BLOCKED_BY_ROBOTS"
        print(f"  {entry['source']:<12} {verdict}")
        print(f"    {entry['reason']}")
        print(f"    queries attempted: {entry['queries_attempted']}, records collected: {entry['records_collected']}")
        for err in entry["errors"]:
            print(f"    ! {err}")
        print()
    print(f"Total records collected: {summary['total_records_collected']}")
    if summary["total_records_collected"] == 0:
        print(
            "No live fares collected. The index continues to run on the synthetic\n"
            "backfill panel (source=\"synthetic\"), which is labelled as modelled\n"
            "rather than observed at every layer. Nothing is fabricated to fill the gap."
        )
    print(f"\nStatus written to {STATUS_PATH}")


if __name__ == "__main__":
    main()
