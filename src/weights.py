"""Load and validate the three fixed weight vectors for the index formula.

Each vector (route, airline, horizon) must sum to 1.0 (CLAUDE.md invariant).
Loading also provides the restriction/one-hot helpers sub-indices use to
reuse the same core aggregation as the headline index (PRD §1.12).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "weights.yaml"

_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Weights:
    route: dict[str, float]
    airline: dict[str, float]
    horizon: dict[int, float]


def _check_sums_to_one(name: str, weights: dict) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > _TOLERANCE:
        raise ValueError(f"{name} weights must sum to 1.0, got {total!r}: {weights!r}")


def load_weights(path: Path = CONFIG_PATH) -> Weights:
    with open(path) as f:
        raw = yaml.safe_load(f)

    route = {k: float(v) for k, v in raw["route"].items()}
    airline = {k: float(v) for k, v in raw["airline"].items()}
    horizon = {int(k): float(v) for k, v in raw["horizon"].items()}

    _check_sums_to_one("route", route)
    _check_sums_to_one("airline", airline)
    _check_sums_to_one("horizon", horizon)

    return Weights(route=route, airline=airline, horizon=horizon)


def one_hot(keys, selected) -> dict:
    """A weight vector with weight 1 on `selected`, 0 on every other key."""
    return {k: (1.0 if k == selected else 0.0) for k in keys}


def restrict_and_renormalize(weights: dict, keys_to_keep) -> dict:
    """Subset `weights` to `keys_to_keep` and rescale so it sums to 1."""
    kept = {k: weights[k] for k in keys_to_keep}
    total = sum(kept.values())
    return {k: v / total for k, v in kept.items()}
