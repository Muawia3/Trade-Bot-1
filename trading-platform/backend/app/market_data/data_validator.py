"""
Market Data Validation and Integrity Engine.
Inspects OHLCV financial time series for pricing anomalies, logical inconsistencies,
timestamp duplicates, weekend/holiday aware gaps, and in-progress unfinished candles.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("market_data.validator")


@dataclass
class CandleValidationResult:
    """Detailed summary of candle dataset validation and cleanup."""
    is_valid: bool
    total_candles: int
    clean_candles: int
    duplicate_count: int
    missing_intervals: List[Tuple[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cleaned_df: Optional[pd.DataFrame] = None
    has_unfinished_candle: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "is_valid": self.is_valid,
            "total_candles": self.total_candles,
            "clean_candles": self.clean_candles,
            "duplicate_count": self.duplicate_count,
            "missing_intervals": self.missing_intervals,
            "errors": self.errors,
            "warnings": self.warnings,
            "has_unfinished_candle": self.has_unfinished_candle,
        }


class DataValidator:
    """
    Validates OHLCV financial data sets.
    Applies mathematical invariants, time continuity checks, and timezone normalization.
    """

    @staticmethod
    def normalize_timestamps(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
        """
        Ensure DataFrame timestamp column is converted to timezone-aware UTC datetime
        and sorted chronologically.
        """
        df_copy = df.copy()
        if time_col in df_copy.columns:
            if not pd.api.types.is_datetime64_any_dtype(df_copy[time_col]):
                df_copy[time_col] = pd.to_datetime(df_copy[time_col], utc=True)
            elif df_copy[time_col].dt.tz is None:
                df_copy[time_col] = df_copy[time_col].dt.tz_localize("UTC")
            else:
                df_copy[time_col] = df_copy[time_col].dt.tz_convert("UTC")

            df_copy = df_copy.sort_values(by=time_col).reset_index(drop=True)
        elif isinstance(df_copy.index, pd.DatetimeIndex):
            if df_copy.index.tz is None:
                df_copy.index = df_copy.index.tz_localize("UTC")
            else:
                df_copy.index = df_copy.index.tz_convert("UTC")
            df_copy = df_copy.sort_index()

        return df_copy

    @staticmethod
    def _is_forex_weekend(t1: datetime, t2: datetime) -> bool:
        """
        Detect if gap between t1 and t2 is purely due to normal weekend closure
        (Friday ~21:00 UTC to Sunday ~21:00 UTC).
        """
        # Friday is weekday 4, Saturday 5, Sunday 6
        if t1.weekday() == 4 and t1.hour >= 20 and t2.weekday() == 6 and t2.hour >= 20:
            return True
        if t1.weekday() == 4 and t2.weekday() == 0 and (t2 - t1).total_seconds() <= 200000:
            return True
        return False

    def validate_candles(
        self,
        df: pd.DataFrame,
        timeframe_minutes: int = 60,
        time_col: str = "time",
        strict: bool = False,
    ) -> CandleValidationResult:
        """
        Validate OHLCV candle dataframe.
        Checks:
        1. Required columns present (open, high, low, close)
        2. Non-negative prices and volume
        3. High >= max(Open, Close) and Low <= min(Open, Close)
        4. Detect duplicates and deduplicate
        5. Missing candle intervals (accounting for weekend breaks)
        6. Identify if the last candle is still forming (unfinished)
        """
        errors: List[str] = []
        warnings: List[str] = []
        missing_intervals: List[Tuple[str, str]] = []

        if df is None or len(df) == 0:
            return CandleValidationResult(
                is_valid=False,
                total_candles=0,
                clean_candles=0,
                duplicate_count=0,
                errors=["Candle DataFrame is empty or None"],
                cleaned_df=pd.DataFrame(),
            )

        # Standardize column names to lowercase
        df_clean = df.copy()
        df_clean.columns = [c.lower() for c in df_clean.columns]

        # Check required columns
        required_cols = ["open", "high", "low", "close"]
        missing_cols = [c for c in required_cols if c not in df_clean.columns]
        if missing_cols:
            return CandleValidationResult(
                is_valid=False,
                total_candles=len(df),
                clean_candles=0,
                duplicate_count=0,
                errors=[f"Missing mandatory OHLC columns: {missing_cols}"],
                cleaned_df=pd.DataFrame(),
            )

        # Normalize timestamps
        time_field = time_col.lower()
        if time_field in df_clean.columns:
            df_clean = self.normalize_timestamps(df_clean, time_col=time_field)
            # Detect duplicates
            dup_mask = df_clean.duplicated(subset=[time_field], keep="first")
            duplicate_count = int(dup_mask.sum())
            if duplicate_count > 0:
                warnings.append(f"Detected {duplicate_count} duplicate candle timestamps. Retaining first occurrence.")
                df_clean = df_clean.drop_duplicates(subset=[time_field], keep="first").reset_index(drop=True)
        else:
            duplicate_count = 0

        total_candles = len(df_clean)

        # Logical price integrity checks
        invalid_prices = (
            (df_clean["open"] <= 0)
            | (df_clean["high"] <= 0)
            | (df_clean["low"] <= 0)
            | (df_clean["close"] <= 0)
        )
        if invalid_prices.any():
            errors.append(f"Found {invalid_prices.sum()} candles with non-positive prices")

        # Invariant: High >= Low
        inverted_high_low = df_clean["high"] < df_clean["low"]
        if inverted_high_low.any():
            errors.append(f"Found {inverted_high_low.sum()} candles where High < Low")

        # Invariant: High >= Open and High >= Close
        invalid_high = (df_clean["high"] < df_clean["open"]) | (df_clean["high"] < df_clean["close"])
        if invalid_high.any():
            msg = f"Found {invalid_high.sum()} candles where High < max(Open, Close)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)
                # Auto-correct High to be max(open, high, close)
                df_clean["high"] = df_clean[["open", "high", "close"]].max(axis=1)

        # Invariant: Low <= Open and Low <= Close
        invalid_low = (df_clean["low"] > df_clean["open"]) | (df_clean["low"] > df_clean["close"])
        if invalid_low.any():
            msg = f"Found {invalid_low.sum()} candles where Low > min(Open, Close)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)
                # Auto-correct Low to be min(open, low, close)
                df_clean["low"] = df_clean[["open", "low", "close"]].min(axis=1)

        # Volume validation
        vol_col = "tick_volume" if "tick_volume" in df_clean.columns else "volume"
        if vol_col in df_clean.columns:
            negative_vol = df_clean[vol_col] < 0
            if negative_vol.any():
                warnings.append(f"Found {negative_vol.sum()} candles with negative volume. Resetting to 0.")
                df_clean.loc[negative_vol, vol_col] = 0

        # Check gap / missing intervals
        if time_field in df_clean.columns and len(df_clean) > 1:
            times = df_clean[time_field].tolist()
            expected_delta = timedelta(minutes=timeframe_minutes)
            max_tolerated_delta = expected_delta * 1.8

            for i in range(len(times) - 1):
                t1 = times[i]
                t2 = times[i + 1]
                delta = t2 - t1

                if delta > max_tolerated_delta:
                    # Ignore normal forex weekend breaks
                    if not self._is_forex_weekend(t1, t2):
                        missing_intervals.append((t1.isoformat(), t2.isoformat()))

            if missing_intervals:
                warnings.append(f"Detected {len(missing_intervals)} unexpected time gaps in market data.")

        # Check for unfinished candle (latest candle still currently open)
        has_unfinished = False
        if time_field in df_clean.columns and len(df_clean) > 0:
            last_candle_time = df_clean[time_field].iloc[-1]
            now_utc = datetime.now(timezone.utc)
            candle_duration = timedelta(minutes=timeframe_minutes)

            # If candle start time + timeframe duration > current time, it is unfinished
            if last_candle_time + candle_duration > now_utc:
                has_unfinished = True
                df_clean["is_complete"] = True
                df_clean.loc[df_clean.index[-1], "is_complete"] = False
            else:
                df_clean["is_complete"] = True

        is_valid = len(errors) == 0

        return CandleValidationResult(
            is_valid=is_valid,
            total_candles=total_candles,
            clean_candles=len(df_clean),
            duplicate_count=duplicate_count,
            missing_intervals=missing_intervals,
            errors=errors,
            warnings=warnings,
            cleaned_df=df_clean,
            has_unfinished_candle=has_unfinished,
        )


# Global validator singleton
data_validator = DataValidator()
