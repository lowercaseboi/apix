"""EaseMyTrip adapter.

Same honest stub as the Ixigo adapter, for the same reason: EaseMyTrip's
robots.txt disallows /flight-search/listing* (and /cheap-flights/) for
User-agent: *, so no fare page has been fetched to write a parser against.
"""

from datetime import date

from src.adapters.base import FareSource
from src.schema import FareRecord

IATA = {"DEL": "DEL", "BOM": "BOM", "BLR": "BLR"}


class EaseMyTripSource(FareSource):
    name = "easemytrip"
    base_url = "https://www.easemytrip.com"

    def fare_search_url(self, route: str, dep_date: date) -> str:
        origin, destination = route.split("-")
        return (
            f"{self.base_url}/flight-search/listing"
            f"?from={IATA[origin]}&to={IATA[destination]}"
            f"&date={dep_date.isoformat()}&adults=1&class=economy"
        )

    def parse_fares(
        self, payload: str, route: str, dep_date: date, horizon: int
    ) -> list[FareRecord]:
        raise NotImplementedError(
            "No parser written: easemytrip.com/robots.txt disallows "
            "/flight-search/listing, so no fare page has been fetched to write one against."
        )
