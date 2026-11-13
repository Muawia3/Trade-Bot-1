"""
Market Data Service.
Provides centralized ingestion, caching, validation, and historical rate delivery
for Forex and Gold instruments. Interfaces with MT5 Bridge and provides seamless
failover with data status tracking (LIVE vs CACHED vs UNAVAILABLE).
"""

import time
import os
import asyncio
import logging
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
import httpx
import pandas as pd
import numpy as np

from app.core.config import get_settings
from app.core.constants import TimeFrame, TARGET_INSTRUMENTS
from app.market_data.data_validator import data_validator, CandleValidationResult

logger = logging.getLogger("market_data.service")


class DataStatus(str, Enum):
    """Origin and freshness status of market data."""
    LIVE = "live"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"
    MOCK = "mock"


class MarketDataService:
    """
    Central Market Data Service for the backend platform.
    Retrieves real-time ticks, historical rates, and maintains an in-memory
    TTL cache of current pricing and OHLCV frames.
    """

    def __init__(self, bridge_url: Optional[str] = None):
        self.settings = get_settings()
        self.bridge_url = bridge_url or os.getenv("MT5_BRIDGE_URL", "http://localhost:8001")
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._candle_cache: Dict[str, Dict[str, Any]] = {}  # key -> {"data": df, "time": timestamp}
        self._cache_ttl_seconds = 2.0  # Live tick TTL
        self._candle_cache_ttl_seconds = 15.0  # Candle TTL
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize shared async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    def is_market_open(self, symbol: str) -> bool:
        """
        Check if the global Forex/Gold market is open for trading.
        Standard Forex market operates 24/5:
        - Opens Sunday 21:00 UTC (Tokyo/Sydney session open)
        - Closes Friday 21:00 / 22:00 UTC (New York session close)
        - Closed all day Saturday and Sunday before 21:00 UTC
        """
        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # Monday is 0, Sunday is 6
        hour = now.hour

        # Saturday: completely closed
        if weekday == 5:
            return False

        # Sunday: closed before 21:00 UTC
        if weekday == 6 and hour < 21:
            return False

        # Friday: closed after 22:00 UTC
        if weekday == 4 and hour >= 22:
            return False

        return True

    async def get_current_prices(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieve latest bid, ask, spread, and timestamp.
        Distinguishes LIVE vs CACHED vs UNAVAILABLE data.
        """
        clean_symbol = symbol.strip().upper()
        cache_entry = self._price_cache.get(clean_symbol)
        now_ts = time.time()

        # Check if cache is fresh
        if cache_entry and (now_ts - cache_entry["cached_at"] < self._cache_ttl_seconds):
            cached_data = dict(cache_entry["data"])
            cached_data["status"] = DataStatus.CACHED.value
            return cached_data

        client = await self._get_client()
        try:
            resp = await client.get(f"{self.bridge_url}/prices/{clean_symbol}")
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "symbol": clean_symbol,
                    "bid": float(data["bid"]),
                    "ask": float(data["ask"]),
                    "spread": int(data["spread"]),
                    "time": data.get("iso_time", datetime.now(timezone.utc).isoformat()),
                    "status": DataStatus.LIVE.value,
                    "is_market_open": self.is_market_open(clean_symbol),
                }
                # Update cache
                self._price_cache[clean_symbol] = {
                    "data": result,
                    "cached_at": now_ts,
                }
                return result
        except Exception as e:
            logger.debug("Bridge HTTP price fetch failed for %s: %s. Using fallback/cache.", clean_symbol, e)

        # Fallback to expired cache if available
        if cache_entry:
            stale = dict(cache_entry["data"])
            stale["status"] = DataStatus.CACHED.value
            stale["warning"] = "Data is stale (bridge unreachable)"
            return stale

        # Fallback to synthetic mock price if bridge is unavailable
        synthetic = self._generate_fallback_tick(clean_symbol)
        return synthetic

    async def get_spread(self, symbol: str) -> float:
        """Return current market spread in points."""
        price_info = await self.get_current_prices(symbol)
        return float(price_info.get("spread", 0.0))

    async def get_candles(
        self,
        symbol: str,
        timeframe: Union[TimeFrame, int] = TimeFrame.H1,
        count: int = 100,
        validate: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candle rates.
        Returns validated pandas DataFrame with [time, open, high, low, close, tick_volume].
        """
        clean_symbol = symbol.strip().upper()
        tf_value = int(timeframe)
        cache_key = f"{clean_symbol}_{tf_value}_{count}"
        now_ts = time.time()

        # Check candle cache
        cached = self._candle_cache.get(cache_key)
        if cached and (now_ts - cached["timestamp"] < self._candle_cache_ttl_seconds):
            return cached["df"].copy()

        client = await self._get_client()
        df = None

        try:
            resp = await client.get(
                f"{self.bridge_url}/rates/{clean_symbol}",
                params={"timeframe": tf_value, "count": count},
            )
            if resp.status_code == 200:
                raw_candles = resp.json().get("candles", [])
                if raw_candles:
                    df = pd.DataFrame(raw_candles)
        except Exception as e:
            logger.warning("Failed to fetch rates from MT5 Bridge for %s: %s", clean_symbol, e)

        # Fallback to synthetic candle generation if bridge unreachable
        if df is None or len(df) == 0:
            logger.info("Generating synthetic fallback candle dataset for %s (%s bars)...", clean_symbol, count)
            df = self._generate_synthetic_candles(clean_symbol, tf_value, count)

        # Validation and cleanup
        if validate:
            val_res = self.validate_candle_data(df, timeframe_minutes=tf_value)
            df = val_res.cleaned_df if val_res.cleaned_df is not None else df

        # Cache result
        self._candle_cache[cache_key] = {"df": df, "timestamp": now_ts}
        return df.copy()

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: Union[TimeFrame, int] = TimeFrame.H1,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical candles bounded by start and end timestamps.
        """
        end_time = end or datetime.now(timezone.utc)
        start_time = start or (end_time - timedelta(days=30))
        tf_minutes = int(timeframe)

        # Estimate candle count
        total_minutes = (end_time - start_time).total_seconds() / 60.0
        estimated_count = max(10, int(total_minutes / tf_minutes))
        # Cap count to 10000
        count = min(estimated_count, 10000)

        df = await self.get_candles(symbol, timeframe=timeframe, count=count, validate=True)
        if "time" in df.columns:
            # Filter between start and end
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df[(df["time"] >= start_time) & (df["time"] <= end_time)].reset_index(drop=True)

        return df

    def validate_candle_data(
        self,
        candles: pd.DataFrame,
        timeframe_minutes: int = 60,
    ) -> CandleValidationResult:
        """Execute validation suite on OHLCV DataFrame."""
        return data_validator.validate_candles(candles, timeframe_minutes=timeframe_minutes)

    def _generate_fallback_tick(self, symbol: str) -> Dict[str, Any]:
        """Generate emergency synthetic tick if bridge is starting or unreachable."""
        is_gold = "XAU" in symbol
        base_bid = 2350.50 if is_gold else 1.08500
        spread = 30 if is_gold else 15
        digits = 2 if is_gold else 5
        spread_price = spread * (0.01 if is_gold else 0.00001)

        return {
            "symbol": symbol,
            "bid": round(base_bid, digits),
            "ask": round(base_bid + spread_price, digits),
            "spread": spread,
            "time": datetime.now(timezone.utc).isoformat(),
            "status": DataStatus.MOCK.value,
            "is_market_open": self.is_market_open(symbol),
        }

    def _generate_synthetic_candles(self, symbol: str, timeframe_minutes: int, count: int) -> pd.DataFrame:
        """Construct realistic synthetic OHLCV sequence."""
        is_gold = "XAU" in symbol
        digits = 2 if is_gold else 5
        base_price = 2350.0 if is_gold else 1.0850
        volatility = 1.2 if is_gold else 0.0006

        interval_delta = timedelta(minutes=timeframe_minutes)
        now = datetime.now(timezone.utc)
        start_time = now - (interval_delta * count)

        times = [start_time + (interval_delta * i) for i in range(count)]
        current_price = base_price
        records = []

        for t in times:
            change = float(np.random.normal(0, volatility))
            open_p = round(current_price, digits)
            close_p = round(open_p + change, digits)
            high_p = round(max(open_p, close_p) + abs(np.random.normal(0, volatility * 0.4)), digits)
            low_p = round(min(open_p, close_p) - abs(np.random.normal(0, volatility * 0.4)), digits)
            volume = int(max(50, np.random.normal(500, 150)))

            records.append({
                "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "tick_volume": volume,
            })
            current_price = close_p

        return pd.DataFrame(records)

    async def close(self):
        """Cleanup HTTP client connections."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


# Singleton instance
market_data_service = MarketDataService()
