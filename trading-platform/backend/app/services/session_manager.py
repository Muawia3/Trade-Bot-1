"""
Trading Session Manager.
Tracks global financial sessions (Asian, London, New York, Overlap),
monitors Forex and Gold market open/close states, and handles weekend/maintenance closures.
"""

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
import zoneinfo

from app.core.constants import TRADING_SESSION_HOURS, TradingSession
from app.core.logging_config import get_logger

logger = get_logger("services.session_manager")


class SessionManager:
    """
    Manages market trading sessions, schedules, instrument-specific trading hours,
    and market open/closed checks.
    """

    def __init__(self):
        # Instrument-specific session profiles (hours in UTC)
        # Gold has a daily rollover/settlement break: 22:00 - 23:00 UTC
        self._instrument_rules: Dict[str, Dict[str, Any]] = {
            "XAUUSD": {
                "daily_break": (22, 23),  # 22:00 to 23:00 UTC break Mon-Thu
                "best_sessions": [TradingSession.LONDON, TradingSession.NEW_YORK, TradingSession.OVERLAP],
            },
            "EURUSD": {
                "daily_break": None,
                "best_sessions": [TradingSession.LONDON, TradingSession.NEW_YORK, TradingSession.OVERLAP],
            },
        }

    def get_utc_now(self) -> datetime:
        """Returns current UTC datetime."""
        return datetime.now(timezone.utc)

    def is_market_open(self, symbol: Optional[str] = None, dt: Optional[datetime] = None) -> bool:
        """
        Determines whether the market is open for trading.
        Accounts for weekend closures (Friday 22:00 UTC to Sunday 21:00 UTC)
        and commodity daily settlement maintenance breaks.
        """
        current_dt = dt or self.get_utc_now()
        weekday = current_dt.weekday()  # Monday is 0, Sunday is 6
        hour = current_dt.hour
        minute = current_dt.minute

        # 1. Weekend closure
        # Friday after 22:00 UTC: closed
        if weekday == 4 and (hour > 22 or (hour == 22 and minute > 0)):
            return False
        # Saturday: closed all day
        if weekday == 5:
            return False
        # Sunday before 21:00 UTC: closed
        if weekday == 6 and hour < 21:
            return False

        # 2. Instrument-specific daily maintenance break
        if symbol:
            rules = self._instrument_rules.get(symbol.upper())
            if rules and rules.get("daily_break"):
                break_start, break_end = rules["daily_break"]
                # Only on Monday-Thursday
                if weekday in (0, 1, 2, 3) and break_start <= hour < break_end:
                    return False

        return True

    def get_active_sessions(self, dt: Optional[datetime] = None) -> List[TradingSession]:
        """
        Returns all trading sessions currently active in UTC.
        """
        current_dt = dt or self.get_utc_now()
        hour = current_dt.hour
        active: List[TradingSession] = []

        for session, (start, end) in TRADING_SESSION_HOURS.items():
            if start <= hour < end:
                active.append(session)

        return active

    def is_session_active(
        self,
        session: TradingSession,
        symbol: Optional[str] = None,
        dt: Optional[datetime] = None,
    ) -> bool:
        """
        Checks if a specific session is currently active and market is open.
        """
        if not self.is_market_open(symbol=symbol, dt=dt):
            return False

        active = self.get_active_sessions(dt=dt)
        return session in active

    def get_current_session(self, dt: Optional[datetime] = None) -> Optional[TradingSession]:
        """
        Returns the primary current session (e.g. OVERLAP takes precedence if active,
        then LONDON, NEW_YORK, ASIAN).
        """
        active = self.get_active_sessions(dt=dt)
        if not active:
            return None

        # Prioritize Overlap as highest liquidity
        if TradingSession.OVERLAP in active:
            return TradingSession.OVERLAP
        if TradingSession.LONDON in active:
            return TradingSession.LONDON
        if TradingSession.NEW_YORK in active:
            return TradingSession.NEW_YORK
        if TradingSession.ASIAN in active:
            return TradingSession.ASIAN

        return active[0]

    def get_next_session_open(self, session: TradingSession, dt: Optional[datetime] = None) -> datetime:
        """
        Calculates the upcoming datetime when the specified session next opens.
        """
        current_dt = dt or self.get_utc_now()
        start_hour, _ = TRADING_SESSION_HOURS[session]

        candidate = current_dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if candidate <= current_dt:
            candidate += timedelta(days=1)

        # Skip weekend if next opening is Saturday or early Sunday
        while not self.is_market_open(dt=candidate.replace(hour=max(start_hour, 1))):
            candidate += timedelta(days=1)

        return candidate

    def get_instrument_session_rating(self, symbol: str, dt: Optional[datetime] = None) -> str:
        """
        Returns liquidity quality rating ('OPTIMAL', 'MODERATE', 'LOW', 'CLOSED')
        for the given instrument right now.
        """
        if not self.is_market_open(symbol=symbol, dt=dt):
            return "CLOSED"

        current_sess = self.get_current_session(dt=dt)
        if not current_sess:
            return "LOW"

        if current_sess == TradingSession.OVERLAP:
            return "OPTIMAL"
        elif current_sess in (TradingSession.LONDON, TradingSession.NEW_YORK):
            return "OPTIMAL" if "XAU" in symbol.upper() else "MODERATE"
        else:
            return "LOW"
