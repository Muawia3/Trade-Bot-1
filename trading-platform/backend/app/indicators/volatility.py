"""
Volatility Indicators: Bollinger Bands, Average True Range (ATR).
Essential for volatility measurement, stop loss sizing, and breakout detection.
"""

from typing import Optional
import numpy as np
import pandas as pd

from app.indicators.base import BaseIndicator


class BollingerBandsIndicator(BaseIndicator):
    """
    Bollinger Bands (BB).
    Calculates Upper Band, Middle Band (SMA), Lower Band, Bandwidth, and %B.
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0, source_col: str = "close"):
        super().__init__(
            name="BB",
            params={"period": period, "std_dev": std_dev, "source_col": source_col},
        )
        self.period = period
        self.std_dev = std_dev
        self.source_col = source_col

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        col = self.source_col.lower()
        matched = [c for c in df_out.columns if c.lower() == col]
        if not matched:
            raise ValueError(f"Source column '{self.source_col}' not found.")
        series = df_out[matched[0]]

        middle = series.rolling(window=self.period, min_periods=self.period).mean()
        std = series.rolling(window=self.period, min_periods=self.period).std()

        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)

        bandwidth = (upper - lower) / middle.replace(0, np.nan)
        percent_b = (series - lower) / (upper - lower).replace(0, np.nan)

        df_out[f"BB_UPPER_{self.period}"] = upper
        df_out[f"BB_MIDDLE_{self.period}"] = middle
        df_out[f"BB_LOWER_{self.period}"] = lower
        df_out[f"BB_BANDWIDTH_{self.period}"] = bandwidth
        df_out[f"BB_PERCENT_B_{self.period}"] = percent_b

        # Generic aliases
        df_out["BB_UPPER"] = upper
        df_out["BB_MIDDLE"] = middle
        df_out["BB_LOWER"] = lower
        df_out["BB_BANDWIDTH"] = bandwidth
        df_out["BB_PERCENT_B"] = percent_b

        return df_out


class ATRIndicator(BaseIndicator):
    """
    Average True Range (ATR) by J. Welles Wilder.
    Measures market volatility in price units.
    """

    def __init__(self, period: int = 14):
        super().__init__(name="ATR", params={"period": period})
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        cols = {c.lower(): c for c in df_out.columns}
        high_col = cols.get("high")
        low_col = cols.get("low")
        close_col = cols.get("close")

        if not (high_col and low_col and close_col):
            raise ValueError("ATR calculation requires 'high', 'low', and 'close' columns.")

        high = df_out[high_col]
        low = df_out[low_col]
        close = df_out[close_col]
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        alpha = 1.0 / self.period
        atr = tr.ewm(alpha=alpha, adjust=False).mean()

        df_out[f"ATR_{self.period}"] = atr
        df_out["ATR"] = atr

        return df_out


def calculate_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """Convenience function to compute Bollinger Bands."""
    return BollingerBandsIndicator(period=period, std_dev=std_dev).calculate(df)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Convenience function to compute ATR."""
    return ATRIndicator(period=period).calculate(df)
