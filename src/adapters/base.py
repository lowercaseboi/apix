"""FareSource interface + the robots.txt compliance gate every adapter
inherits.

Neither CLAUDE.md nor the PRD defines this interface — both only reference
"the FareSource interface" and "the adapter registry" — so the method names
and signatures here are a design decision.

The compliance gate is not decoration. CLAUDE.md lists respecting
robots.txt as non-negotiable, so fetch() evaluates robots.txt and raises
before issuing any request to a disallowed fare-search path. A blocked
platform reduces coverage; it never crashes the pipeline and never
substitutes fabricated data (PRD §1.7, graceful degradation).
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.schema import FareRecord

# Honest identification per CLAUDE.md ("Identify the agent honestly in the
# user-agent string"). Neither document specifies the string's contents —
# this names the project and its purpose and does not impersonate a browser.
USER_AGENT = (
    "APIx-bot/0.1 (+https://github.com/mospi-apix; "
    "airfare price index research for MoSPI, SIH 2026 PS 26056)"
)

# Assumption: no numeric rate limit exists in either document — the PRD says
# only "generous rate limiting" and "well below normal human browsing
# volume" for a 42-query daily cycle. 5s between requests puts a full cycle
# at ~4 minutes, far below what a human browsing flight prices would issue.
MIN_REQUEST_INTERVAL_SECONDS = 5.0

REQUEST_TIMEOUT_SECONDS = 20.0


class RobotsDisallowed(Exception):
    """Raised instead of fetching a path the platform's robots.txt disallows."""


@dataclass(frozen=True)
class ComplianceStatus:
    source: str
    fare_search_url: str
    robots_allowed: bool
    reason: str
    checked_at: datetime

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "fare_search_url": self.fare_search_url,
            "robots_allowed": self.robots_allowed,
            "reason": self.reason,
            "checked_at": self.checked_at.isoformat(),
        }


class FareSource(ABC):
    name: str
    base_url: str

    def __init__(self) -> None:
        self._last_request_at = 0.0

    @abstractmethod
    def fare_search_url(self, route: str, dep_date: date) -> str:
        """The public fare-display URL this adapter would query."""

    @abstractmethod
    def parse_fares(
        self, payload: str, route: str, dep_date: date, horizon: int
    ) -> list[FareRecord]:
        """Convert a fetched fare page into canonical FareRecords."""

    def check_compliance(self, route: str | None = None, dep_date: date | None = None) -> ComplianceStatus:
        probe_url = self.fare_search_url(route or "DEL-BOM", dep_date or date.today())
        robots_url = urljoin(self.base_url, "/robots.txt")

        parser = RobotFileParser()
        try:
            response = httpx.get(
                robots_url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Unreadable robots.txt is treated as disallowed: the polite
            # reading when we cannot confirm permission.
            return ComplianceStatus(
                source=self.name,
                fare_search_url=probe_url,
                robots_allowed=False,
                reason=f"robots.txt could not be read ({exc.__class__.__name__}); treating as disallowed",
                checked_at=datetime.now(timezone.utc),
            )

        parser.parse(response.text.splitlines())
        allowed = parser.can_fetch(USER_AGENT, probe_url)
        path = urlparse(probe_url).path
        return ComplianceStatus(
            source=self.name,
            fare_search_url=probe_url,
            robots_allowed=allowed,
            reason=(
                f"robots.txt permits {path}"
                if allowed
                else f"robots.txt disallows {path}"
            ),
            checked_at=datetime.now(timezone.utc),
        )

    def fetch(self, route: str, dep_date: date, horizon: int) -> list[FareRecord]:
        status = self.check_compliance(route, dep_date)
        if not status.robots_allowed:
            raise RobotsDisallowed(f"{self.name}: {status.reason}")

        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)

        url = self.fare_search_url(route, dep_date)
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return self.parse_fares(response.text, route, dep_date, horizon)
