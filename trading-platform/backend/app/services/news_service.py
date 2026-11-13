"""
Macroeconomic News and Economic Calendar Service.

Monitors scheduled high-impact events (FOMC, NFP, CPI, Central Bank Interest Rate decisions)
and determines trading blackout windows to prevent catastrophic slippage, spread widening,
and execution failures during tier-1 economic releases.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from app.core.config import get_settings
from app.core.constants import FOREX_PAIRS, GOLD_INSTRUMENTS
from app.core.logging_config import get_logger
from app.services.news_provider import (
    EconomicEvent,
    EventImpact,
    ExternalAPIProvider,
    MockNewsProvider,
    NewsProvider,
)

logger = get_logger("app.services.news_service")

# Critical high-impact macroeconomic event keywords
KEY_EVENT_KEYWORDS: Set[str] = {
    "cpi",
    "consumer price index",
    "nfp",
    "non-farm payroll",
    "non farm payrolls",
    "fomc",
    "federal funds rate",
    "interest rate decision",
    "ecb interest rate",
    "boe interest rate",
    "gdp",
    "gross domestic product",
    "pmi",
    "manufacturing pmi",
    "services pmi",
    "unemployment rate",
    "central bank",
    "powell",
    "lagarde",
}


class NewsService:
    """
    Service responsible for macroeconomic awareness and pre/post-news trade restrictions.

    Enforces strict risk safety: never invents false events, and logs warnings
    if news feeds are unavailable or unconfigured.
    """

    def __init__(
        self,
        provider: Optional[NewsProvider] = None,
        pre_event_buffer_minutes: int = 30,
        post_event_buffer_minutes: int = 15,
    ) -> None:
        """
        Initialize the NewsService.

        Args:
            provider: Concrete NewsProvider instance. If None, auto-initializes based on app configuration.
            pre_event_buffer_minutes: Window before event where new positions are blocked.
            post_event_buffer_minutes: Window after event where market is allowed to stabilize.
        """
        self.settings = get_settings()
        self.pre_event_buffer_minutes = pre_event_buffer_minutes
        self.post_event_buffer_minutes = post_event_buffer_minutes

        if provider is not None:
            self.provider = provider
        elif self.settings.NEWS_API_KEY:
            self.provider = ExternalAPIProvider(
                api_key=self.settings.NEWS_API_KEY,
                provider_name=self.settings.NEWS_API_PROVIDER or "ExternalNewsAPI",
            )
        else:
            logger.warning(
                "NEWS_API_KEY not found in settings. Initializing ExternalAPIProvider in unconfigured mode. "
                "No live news events will be tracked. To test, supply a MockNewsProvider."
            )
            self.provider = ExternalAPIProvider(api_key=None)

    def get_upcoming_events(
        self,
        currencies: Optional[List[str]] = None,
        hours_ahead: int = 24,
    ) -> List[EconomicEvent]:
        """
        Retrieve upcoming macroeconomic events within the specified forward window.

        Args:
            currencies: Currency codes to filter (defaults to ['USD', 'EUR', 'GBP']).
            hours_ahead: Forward horizon in hours.

        Returns:
            List of EconomicEvent objects ordered chronologically.
        """
        target_currencies = currencies or ["USD", "EUR", "GBP"]
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours_ahead)

        try:
            events = self.provider.fetch_events(
                currencies=target_currencies,
                start_time=now - timedelta(minutes=self.post_event_buffer_minutes),
                end_time=end_time,
            )
            return events
        except Exception as exc:
            logger.error("Failed to fetch upcoming economic events: %s", exc, exc_info=True)
            return []

    def is_high_impact_upcoming(
        self,
        symbol: str,
        minutes_before: int = 30,
    ) -> bool:
        """
        Check if any high-impact economic release is scheduled within the next N minutes.

        Args:
            symbol: Financial instrument (e.g., 'XAUUSD', 'EURUSD').
            minutes_before: Lead time window in minutes.

        Returns:
            True if a tier-1 event is imminent, False otherwise.
        """
        currencies = self.get_currencies_for_symbol(symbol)
        now = datetime.utcnow()
        cutoff_time = now + timedelta(minutes=minutes_before)

        events = self.get_upcoming_events(currencies=currencies, hours_ahead=2)

        for event in events:
            if event.impact == EventImpact.HIGH:
                if now <= event.datetime <= cutoff_time:
                    logger.warning(
                        "High impact event '%s' (%s) scheduled at %s UTC (in %.1f minutes)",
                        event.name,
                        event.currency,
                        event.datetime.isoformat(),
                        (event.datetime - now).total_seconds() / 60.0,
                    )
                    return True
        return False

    def should_restrict_trading(self, symbol: str) -> Tuple[bool, str]:
        """
        Evaluate whether new order entry for a symbol should be prohibited due to news volatility.

        Checks both pre-event anticipation window and post-event stabilization window.

        Args:
            symbol: Financial instrument.

        Returns:
            Tuple of (restrict_flag, rationale_message).
        """
        currencies = self.get_currencies_for_symbol(symbol)
        now = datetime.utcnow()

        # Query events from recently passed buffer to upcoming buffer
        events = self.get_upcoming_events(currencies=currencies, hours_ahead=2)

        if not events:
            return False, "No active macroeconomic blackout windows."

        for event in events:
            # Check if event is designated HIGH impact or matches tier-1 keywords
            is_tier_1 = (
                event.impact == EventImpact.HIGH
                or any(kw in event.name.lower() for kw in KEY_EVENT_KEYWORDS)
            )

            if not is_tier_1:
                continue

            event_time = event.datetime
            pre_window_start = event_time - timedelta(minutes=self.pre_event_buffer_minutes)
            post_window_end = event_time + timedelta(minutes=self.post_event_buffer_minutes)

            # Within blackout zone
            if pre_window_start <= now <= post_window_end:
                minutes_delta = (event_time - now).total_seconds() / 60.0
                if minutes_delta > 0:
                    reason = (
                        f"Trading RESTRICTED: High-impact release '{event.name}' ({event.currency}) "
                        f"is scheduled in {int(minutes_delta)} minutes. Order entries blocked."
                    )
                else:
                    reason = (
                        f"Trading RESTRICTED: High-impact release '{event.name}' ({event.currency}) "
                        f"occurred {int(abs(minutes_delta))} minutes ago. Awaiting market stabilization."
                    )
                logger.info(reason)
                return True, reason

        return False, "Clear of impending high-impact economic releases."

    @staticmethod
    def get_currencies_for_symbol(symbol: str) -> List[str]:
        """
        Deconstruct instrument symbol into its component currencies.

        Examples:
            'EURUSD' -> ['EUR', 'USD']
            'XAUUSD' -> ['USD']
            'GBPJPY' -> ['GBP', 'JPY']
        """
        sym = symbol.upper().strip()

        # Metals priced against USD
        if sym in ("XAUUSD", "GOLD", "XAGUSD", "SILVER"):
            return ["USD"]

        if len(sym) == 6:
            return [sym[:3], sym[3:]]

        # General extraction
        common = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
        detected = [c for c in common if c in sym]
        return detected if detected else ["USD"]
