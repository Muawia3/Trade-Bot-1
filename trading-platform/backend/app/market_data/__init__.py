"""
Market Data Engine Package.
Provides price validation, data ingestion, caching, and real-time WebSocket feeds.
"""

from app.market_data.data_validator import (
    DataValidator,
    data_validator,
    CandleValidationResult,
)
from app.market_data.market_data_service import (
    MarketDataService,
    market_data_service,
    DataStatus,
)
from app.market_data.price_feed import (
    PriceFeed,
    price_feed,
    PriceHistoryBuffer,
)

__all__ = [
    "DataValidator",
    "data_validator",
    "CandleValidationResult",
    "MarketDataService",
    "market_data_service",
    "DataStatus",
    "PriceFeed",
    "price_feed",
    "PriceHistoryBuffer",
]
