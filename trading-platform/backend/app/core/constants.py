"""
Application-wide constants and enumerations.
"""

from enum import Enum, IntEnum
from typing import Dict, Tuple


# =============================================================================
# Timeframes — values match MT5 TIMEFRAME constants
# =============================================================================

class TimeFrame(IntEnum):
    M1 = 1
    M5 = 5
    M15 = 15
    M30 = 30
    H1 = 60
    H4 = 240
    D1 = 1440
    W1 = 10080
    MN1 = 43200


# =============================================================================
# Trading Sessions (UTC hours)
# =============================================================================

class TradingSession(str, Enum):
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"


TRADING_SESSION_HOURS: Dict[TradingSession, Tuple[int, int]] = {
    TradingSession.ASIAN: (0, 9),       # 00:00 – 09:00 UTC
    TradingSession.LONDON: (7, 16),     # 07:00 – 16:00 UTC
    TradingSession.NEW_YORK: (12, 21),  # 12:00 – 21:00 UTC
    TradingSession.OVERLAP: (12, 16),   # 12:00 – 16:00 UTC (London–NY overlap)
}


# =============================================================================
# Order & Position Enums
# =============================================================================

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class PositionType(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CLOSED = "closed"
    EXPIRED = "expired"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


# =============================================================================
# Target Instruments
# =============================================================================

FOREX_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "NZDUSD", "USDCAD",
    "EURGBP", "EURJPY", "GBPJPY",
    "EURAUD", "EURNZD", "GBPAUD",
    "AUDNZD", "AUDCAD", "AUDCHF",
    "CADJPY", "CHFJPY", "NZDJPY",
]

GOLD_INSTRUMENTS = [
    "XAUUSD",  # Gold vs USD (primary)
    "XAGUSD",  # Silver vs USD
]

TARGET_INSTRUMENTS = FOREX_PAIRS + GOLD_INSTRUMENTS


# =============================================================================
# Risk Constants
# =============================================================================

DEFAULT_STOP_LOSS_PIPS = 50
DEFAULT_TAKE_PROFIT_PIPS = 100
MIN_LOT_SIZE = 0.01
MAX_LOT_SIZE = 100.0
DEFAULT_LOT_SIZE = 0.1


# =============================================================================
# API Constants
# =============================================================================

API_V1_PREFIX = "/api/v1"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30
