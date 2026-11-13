"""
Comprehensive Indicator Calculator.
Computes standard indicator suites across DataFrames and produces snapshots.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from app.core.logging_config import get_logger
from app.indicators.momentum import MACDIndicator, RSIIndicator, StochasticRSIIndicator
from app.indicators.trend import ADXIndicator, EMAIndicator, SMAIndicator
from app.indicators.volatility import ATRIndicator, BollingerBandsIndicator
from app.indicators.volume import OBVIndicator, VolumeSMAIndicator, VWAPIndicator

logger = get_logger("indicators.calculator")


class IndicatorCalculator:
    """
    Orchestrates calculation of trend, momentum, volatility, and volume indicators.
    """

    def __init__(
        self,
        ema_periods: Optional[List[int]] = None,
        sma_periods: Optional[List[int]] = None,
        adx_period: int = 14,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        stoch_rsi_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        atr_period: int = 14,
        vol_sma_period: int = 20,
    ):
        self.ema_periods = ema_periods or [20, 50, 200]
        self.sma_periods = sma_periods or [20, 50, 200]
        self.adx_period = adx_period
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stoch_rsi_period = stoch_rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.atr_period = atr_period
        self.vol_sma_period = vol_sma_period

        # Instantiate indicators
        self.ema_ind = EMAIndicator(periods=self.ema_periods)
        self.sma_ind = SMAIndicator(periods=self.sma_periods)
        self.adx_ind = ADXIndicator(period=self.adx_period)
        self.rsi_ind = RSIIndicator(period=self.rsi_period)
        self.macd_ind = MACDIndicator(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal)
        self.stoch_rsi_ind = StochasticRSIIndicator(period=self.stoch_rsi_period, rsi_period=self.rsi_period)
        self.bb_ind = BollingerBandsIndicator(period=self.bb_period, std_dev=self.bb_std)
        self.atr_ind = ATRIndicator(period=self.atr_period)
        self.vwap_ind = VWAPIndicator()
        self.vol_sma_ind = VolumeSMAIndicator(period=self.vol_sma_period)
        self.obv_ind = OBVIndicator()

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates all indicator suites sequentially on the provided DataFrame.

        Args:
            df: DataFrame containing at minimum OHLC data.

        Returns:
            DataFrame enriched with all computed indicator columns.
        """
        if df.empty or len(df) < 5:
            logger.warning("DataFrame too small to calculate indicators reliably (rows=%d)", len(df))
            return df

        try:
            df_out = self.ema_ind.calculate(df)
            df_out = self.sma_ind.calculate(df_out)
            df_out = self.adx_ind.calculate(df_out)
            df_out = self.rsi_ind.calculate(df_out)
            df_out = self.macd_ind.calculate(df_out)
            df_out = self.stoch_rsi_ind.calculate(df_out)
            df_out = self.bb_ind.calculate(df_out)
            df_out = self.atr_ind.calculate(df_out)
            df_out = self.vwap_ind.calculate(df_out)
            df_out = self.vol_sma_ind.calculate(df_out)
            df_out = self.obv_ind.calculate(df_out)
            return df_out
        except Exception as e:
            logger.error("Error computing indicators: %s", str(e), exc_info=True)
            raise


def get_indicator_snapshot(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates all indicators if not already calculated, and extracts the latest
    snapshot of values as a dictionary.

    Args:
        df: DataFrame with OHLCV data or precomputed indicator columns.

    Returns:
        Dictionary mapping indicator names to their latest numeric values.
    """
    if df.empty:
        return {}

    # Check if indicators are missing
    if "RSI_14" not in df.columns or "EMA_20" not in df.columns or "ATR" not in df.columns:
        calculator = IndicatorCalculator()
        df = calculator.calculate_all(df)

    latest = df.iloc[-1]
    cols = {c.lower(): c for c in df.columns}

    def safe_val(key: str, default: Optional[float] = None) -> Optional[float]:
        if key in df.columns and pd.notna(latest[key]):
            return float(latest[key])
        lower_match = cols.get(key.lower())
        if lower_match and pd.notna(latest[lower_match]):
            return float(latest[lower_match])
        return default

    snapshot: Dict[str, Any] = {
        "close": safe_val("close"),
        "open": safe_val("open"),
        "high": safe_val("high"),
        "low": safe_val("low"),
        "volume": safe_val("volume", safe_val("tick_volume", 0.0)),
        "ema_20": safe_val("EMA_20"),
        "ema_50": safe_val("EMA_50"),
        "ema_200": safe_val("EMA_200"),
        "sma_20": safe_val("SMA_20"),
        "sma_50": safe_val("SMA_50"),
        "sma_200": safe_val("SMA_200"),
        "adx": safe_val("ADX_14"),
        "plus_di": safe_val("PLUS_DI_14"),
        "minus_di": safe_val("MINUS_DI_14"),
        "rsi": safe_val("RSI_14"),
        "macd": safe_val("MACD"),
        "macd_signal": safe_val("MACD_SIGNAL"),
        "macd_hist": safe_val("MACD_HIST"),
        "stoch_rsi_k": safe_val("STOCH_RSI_K"),
        "stoch_rsi_d": safe_val("STOCH_RSI_D"),
        "bb_upper": safe_val("BB_UPPER"),
        "bb_middle": safe_val("BB_MIDDLE"),
        "bb_lower": safe_val("BB_LOWER"),
        "bb_bandwidth": safe_val("BB_BANDWIDTH"),
        "bb_percent_b": safe_val("BB_PERCENT_B"),
        "atr": safe_val("ATR"),
        "vwap": safe_val("VWAP"),
        "vol_sma": safe_val("VOL_SMA"),
        "obv": safe_val("OBV"),
    }

    # Add timestamp if present
    if "time" in cols:
        time_val = latest[cols["time"]]
        snapshot["timestamp"] = str(time_val)
    elif isinstance(df.index, pd.DatetimeIndex):
        snapshot["timestamp"] = str(df.index[-1])

    return snapshot
