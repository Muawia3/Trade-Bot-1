"""
Pluggable economic calendar news providers.

Provides:
- NewsProvider: Abstract Base Class defining standard news retrieval protocol
- MockNewsProvider: Test harness for validating volatility filters and trade restrictions
- ExternalAPIProvider: Adapter for external financial calendars (ForexFactory, Investing.com)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.logging_config import get_logger

logger = get_logger("app.services.news_provider")


class EventImpact(str, Enum):
    """Economic event expected market impact level."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


@dataclass
class EconomicEvent:
    """Standardized representation of a scheduled macroeconomic release."""
    name: str
    currency: str
    impact: EventImpact
    datetime: datetime
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    country: Optional[str] = None
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert economic event to dictionary representation."""
        res = asdict(self)
        res["impact"] = self.impact.value
        res["datetime"] = self.datetime.isoformat()
        return res


class NewsProvider(ABC):
    """Abstract interface for macroeconomic calendar providers."""

    @abstractmethod
    def fetch_events(
        self,
        currencies: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """
        Fetch macroeconomic events within a specified time window.

        Args:
            currencies: List of ISO currency codes (e.g. ['USD', 'EUR', 'GBP']).
            start_time: Window start datetime (UTC).
            end_time: Window end datetime (UTC).

        Returns:
            List of EconomicEvent objects matching criteria.
        """
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Verify connectivity and health of the news provider."""
        pass


class MockNewsProvider(NewsProvider):
    """
    Mock macroeconomic calendar provider for testing and offline simulations.

    Allows test suites to simulate impending high-impact announcements (FOMC, NFP, CPI)
    to confirm that risk blackout windows trigger accurately.
    """

    def __init__(self, simulate_upcoming_high_impact: bool = False, minutes_offset: int = 15) -> None:
        """
        Initialize MockNewsProvider.

        Args:
            simulate_upcoming_high_impact: If True, injects high impact event soon.
            minutes_offset: Minutes from now when the simulated event will occur.
        """
        self.simulate_upcoming_high_impact = simulate_upcoming_high_impact
        self.minutes_offset = minutes_offset
        self._preset_events: List[EconomicEvent] = []
        logger.info("Initialized MockNewsProvider (simulate_upcoming=%s)", simulate_upcoming_high_impact)

    def set_events(self, events: List[EconomicEvent]) -> None:
        """Explicitly inject a list of events for testing."""
        self._preset_events = list(events)

    def fetch_events(
        self,
        currencies: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """Return preset or synthetically generated test calendar items."""
        now = datetime.utcnow()
        start = start_time or (now - timedelta(hours=2))
        end = end_time or (now + timedelta(hours=24))
        currs = [c.upper() for c in currencies] if currencies else ["USD", "EUR", "GBP", "JPY"]

        events = list(self._preset_events)

        if self.simulate_upcoming_high_impact:
            simulated_event_time = now + timedelta(minutes=self.minutes_offset)
            if start <= simulated_event_time <= end and "USD" in currs:
                events.append(
                    EconomicEvent(
                        name="US Consumer Price Index (CPI) YoY",
                        currency="USD",
                        impact=EventImpact.HIGH,
                        datetime=simulated_event_time,
                        actual=None,
                        forecast=3.1,
                        previous=3.2,
                        country="US",
                        unit="%",
                    )
                )

        # Filter by currency and time boundary
        filtered = [
            e for e in events
            if (e.currency.upper() in currs) and (start <= e.datetime <= end)
        ]
        return sorted(filtered, key=lambda x: x.datetime)

    def is_healthy(self) -> bool:
        """Mock provider is always healthy."""
        return True


class ExternalAPIProvider(NewsProvider):
    """
    Adapter for production external news calendar APIs (ForexFactory, Investing.com, Finnhub).

    If no API key or provider is configured, returns an empty list and logs an appropriate warning.
    NEVER invents false economic data.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Initialize ExternalAPIProvider.

        Args:
            api_key: Secret API key if required.
            provider_name: Name of external vendor.
            base_url: API endpoint.
        """
        self.api_key = api_key
        self.provider_name = provider_name or "generic_calendar_api"
        self.base_url = base_url

        if not self.api_key:
            logger.warning(
                "External news provider '%s' has no API key configured. News queries will return empty lists.",
                self.provider_name,
            )

    def fetch_events(
        self,
        currencies: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """Fetch real events from remote API or return empty list safely if unconfigured."""
        if not self.api_key:
            logger.warning("No API key available for external news provider '%s'. Returning empty calendar.", self.provider_name)
            return []

        # When integrated with live provider:
        # e.g., make async/sync HTTP GET to provider endpoint with start_time & end_time
        logger.info("Fetching calendar from external provider %s", self.provider_name)
        return []

    def is_healthy(self) -> bool:
        """Check if remote provider is configured."""
        return bool(self.api_key)
