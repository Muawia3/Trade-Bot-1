"""
Volume Indicators: VWAP, Volume SMA, On-Balance Volume (OBV).
Supports MT5 tick volume and real volume.
"""

from typing import Optional
import numpy as np
import pandas as pd

from app.indicators.base import BaseIndicator


def _extract_volume_series(df: pd.DataFrame) -> pd.Series:
    """Helper to detect tick_volume or volume column."""
    cols = {c.lower(): c for c in df.columns}
    if "tick_volume" in cols:
        return df[cols["tick_volume"]].astype(float)
    if "volume" in cols:
        return df[cols["volume"]].astype(float)
    if "real_volume" in cols:
        return df[cols["real_volume"]].astype(float)
    # Default fallback to ones if volume not available
    return pd.Series(1.0, index=df.index)


class VWAPIndicator(BaseIndicator):
    """
    Volume Weighted Average Price (VWAP).
    Computes cumulative VWAP reset daily (if datetime index or 'time' available)
    or rolling VWAP.
    """

    def __init__(self, rolling_window: Optional[int] = None):
        super().__init__(name="VWAP", params={"rolling_window": rolling_window})
        self.rolling_window = rolling_window

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        cols = {c.lower(): c for c in df_out.columns}
        high = df_out[cols.get("high", "high")]
        low = df_out[cols.get("low", "low")]
        close = df_out[cols.get("close", "close")]
        volume = _extract_volume_series(df_out)

        typical_price = (high + low + close) / 3.0
        pv = typical_price * volume

        if self.rolling_window:
            rolling_pv = pv.rolling(window=self.rolling_window, min_periods=1).sum()
            rolling_vol = volume.rolling(window=self.rolling_window, min_periods=1).sum()
            vwap = rolling_pv / rolling_vol.replace(0, np.nan)
        else:
            # Check if we can group by date
            time_series = None
            if isinstance(df_out.index, pd.DatetimeIndex):
                time_series = df_out.index.date
            elif "time" in cols and pd.api.types.is_datetime64_any_dtype(df_out[cols["time"]]):
                time_series = df_out[cols["time"]].dt.date

            if time_series is not None:
                df_temp = pd.DataFrame({"pv": pv, "vol": volume, "date": time_series}, index=df_out.index)
                cum_pv = df_temp.groupby("date")["pv"].cumsum()
                cum_vol = df_temp.groupby("date")["vol"].cumsum()
                vwap = cum_pv / cum_vol.replace(0, np.nan)
            else:
                # Cumulative over entire dataset
                cum_pv = pv.cumsum()
                cum_vol = volume.cumsum()
                vwap = cum_pv / cum_vol.replace(0, np.nan)

        df_out["VWAP"] = vwap
        return df_out


class VolumeSMAIndicator(BaseIndicator):
    """Simple Moving Average of Volume."""

    def __init__(self, period: int = 20):
        super().__init__(name="VOL_SMA", params={"period": period})
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        volume = _extract_volume_series(df_out)
        vol_sma = volume.rolling(window=self.period, min_periods=1).mean()
        df_out[f"VOL_SMA_{self.period}"] = vol_sma
        df_out["VOL_SMA"] = vol_sma
        return df_out


class OBVIndicator(BaseIndicator):
    """On-Balance Volume (OBV)."""

    def __init__(self):
        super().__init__(name="OBV")

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        cols = {c.lower(): c for c in df_out.columns}
        close = df_out[cols.get("close", "close")]
        volume = _extract_volume_series(df_out)

        price_diff = close.diff()
        direction = np.where(price_diff > 0, 1.0, np.where(price_diff < 0, -1.0, 0.0))
        obv = (direction * volume).cumsum()
        df_out["OBV"] = obv
        return df_out


def calculate_vwap(df: pd.DataFrame, rolling_window: Optional[int] = None) -> pd.DataFrame:
    """Convenience function to compute VWAP."""
    return VWAPIndicator(rolling_window=rolling_window).calculate(df)


def calculate_volume_sma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Convenience function to compute Volume SMA."""
    return VolumeSMAIndicator(period=period).calculate(df)


def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience function to compute OBV."""
    return OBVIndicator().calculate(df)
