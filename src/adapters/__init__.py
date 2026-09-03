"""The adapter registry. Adding a platform means adding one class here and
touching nothing else — the index engine is source-agnostic by design.
"""

from src.adapters.base import ComplianceStatus, FareSource, RobotsDisallowed
from src.adapters.easemytrip import EaseMyTripSource
from src.adapters.ixigo import IxigoSource

REGISTRY: dict[str, type[FareSource]] = {
    "ixigo": IxigoSource,
    "easemytrip": EaseMyTripSource,
}


def get_source(name: str) -> FareSource:
    return REGISTRY[name]()


__all__ = [
    "REGISTRY",
    "ComplianceStatus",
    "FareSource",
    "RobotsDisallowed",
    "get_source",
]
