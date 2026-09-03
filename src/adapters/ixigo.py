"""Ixigo adapter.

parse_fares is an honest stub. Ixigo's robots.txt disallows /flights/search
(and /search/result/ and /api/) for User-agent: *, so no fare page has ever
been fetched — writing a speculative parser against a page we cannot
legally retrieve would be inventing a capability we do not have. The PRD
sanctions exactly this fallback: "commit the adapter interface with a stub
implementation... A partially-working scraper honestly framed beats a demo
that crashes."

If a formal data-sharing agreement replaced scraping (PRD §1.14's stated
production path), only parse_fares below would need writing.
"""

from datetime import date

from src.adapters.base import FareSource
from src.schema import FareRecord

IATA = {"DEL": "DEL", "BOM": "BOM", "BLR": "BLR"}


class IxigoSource(FareSource):
    name = "ixigo"
    base_url = "https://www.ixigo.com"

    def fare_search_url(self, route: str, dep_date: date) -> str:
        origin, destination = route.split("-")
        return (
            f"{self.base_url}/flights/search"
            f"?from={IATA[origin]}&to={IATA[destination]}"
            f"&date={dep_date.isoformat()}&adults=1&class=economy"
        )

    def parse_fares(
        self, payload: str, route: str, dep_date: date, horizon: int
    ) -> list[FareRecord]:
        raise NotImplementedError(
            "No parser written: ixigo.com/robots.txt disallows /flights/search, "
            "so no fare page has been fetched to write one against."
        )
