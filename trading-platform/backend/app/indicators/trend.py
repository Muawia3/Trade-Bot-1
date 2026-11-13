"""
Trend Indicators: EMA, SMA, ADX.
Provides vectorized calculations for trend detection and trend strength.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from app.indicators.base import BaseIndicator


class EMAIndicator(BaseIndicator):
    """Exponential Moving Average (EMA)."""

    def __init__(self, periods: Optional[List[int]] = None, source_col: str = "close"):
        periods = periods or [20, 50, 200]
        super().__init__(name="EMA", params={"periods": periods, "source_col": source_col})
        self.periods = periods
        self.source_col = source_col

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates EMA for configured periods on the specified source column.
        """
        df_out = df.copy()
        col = self.source_col.lower()
        if col not in df_out.columns:
            # fallback to lowercase or uppercase column matching
            matched = [c for c in df_out.columns if c.lower() == col]
            if matched:
                col = matched[0]
            else:
                raise ValueError(f"Source column '{self.source_col}' not found in DataFrame.")

        for period in self.periods:
            col_name = f"EMA_{period}"
            df_out[col_name] = df_out[col].ewm(span=period, adjust=False).mean()

        return df_out


class SMAIndicator(BaseIndicator):
    """Simple Moving Average (SMA)."""

    def __init__(self, periods: Optional[List[int]] = None, source_col: str = "close"):
        periods = periods or [20, 50, 200]
        super().__init__(name="SMA", params={"periods": periods, "source_col": source_col})
        self.periods = periods
        self.source_col = source_col

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates SMA for configured periods on the specified source column.
        """
        df_out = df.copy()
        col = self.source_col.lower()
        if col not in df_out.columns:
            matched = [c for c in df_out.columns if c.lower() == col]
            if matched:
                col = matched[0]
            else:
                raise ValueError(f"Source column '{self.source_col}' not found in DataFrame.")

        for period in self.periods:
            col_name = f"SMA_{period}"
            df_out[col_name] = df_out[col].rolling(window=period, min_periods=period).mean()

        return df_out


class ADXIndicator(BaseIndicator):
    """
    Average Directional Index (ADX) by J. Welles Wilder.
    Measures trend strength regardless of direction.
    Appends: ADX_{period}, PLUS_DI_{period}, MINUS_DI_{period}.
    """

    def __init__(self, period: int = 14):
        super().__init__(name="ADX", params={"period": period})
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates ADX, +DI, and -DI.
        """
        df_out = df.copy()
        cols = {c.lower(): c for c in df_out.columns}
        high_col = cols.get("high")
        low_col = cols.get("low")
        close_col = cols.get("close")

        if not (high_col and low_col and close_col):
            raise ValueError("ADX calculation requires 'high', 'low', and 'close' columns.")

        high = df_out[high_col]
        low = df_out[low_col]
        close = df_out[close_col]
        prev_close = close.shift(1)

        # True Range
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        plus_dm_s = pd.Series(plus_dm, index=df_out.index)
        minus_dm_s = pd.Series(minus_dm, index=df_out.index)

        # Wilder's smoothing (alpha = 1 / period)
        alpha = 1.0 / self.period
        atr = tr.ewm(alpha=alpha, adjust=False).mean()
        plus_di = 100 * (plus_dm_s.ewm(alpha=alpha, adjust=False).mean() / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm_s.ewm(alpha=alpha, adjust=False).mean() / atr.replace(0, np.nan))

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx = dx.ewm(alpha=alpha, adjust=False).mean()

        df_out[f"ADX_{self.period}"] = adx
        df_out[f"PLUS_DI_{self.period}"] = plus_di
        df_out[f"MINUS_DI_{self.period}"] = minus_di

        return df_out


def calculate_ema(df: pd.DataFrame, periods: Optional[List[int]] = None) -> pd.DataFrame:
    """Convenience function to compute EMAs."""
    return EMAIndicator(periods=periods).calculate(df)


def calculate_sma(df: pd.DataFrame, periods: Optional[List[int]] = None) -> pd.DataFrame:
    """Convenience function to compute SMAs."""
    return SMAIndicator(periods=periods).calculate(df)


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Convenience function to compute ADX."""
    return ADXIndicator(period=period).calculate(df)
