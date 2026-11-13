"""
Momentum Indicators: RSI, MACD, Stochastic RSI.
Provides oscillator calculations for oversold/overbought and momentum shifts.
"""

from typing import Optional
import numpy as np
import pandas as pd

from app.indicators.base import BaseIndicator


class RSIIndicator(BaseIndicator):
    """
    Relative Strength Index (RSI).
    Measures speed and change of price movements.
    """

    def __init__(self, period: int = 14, source_col: str = "close"):
        super().__init__(name="RSI", params={"period": period, "source_col": source_col})
        self.period = period
        self.source_col = source_col

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        col = self.source_col.lower()
        matched = [c for c in df_out.columns if c.lower() == col]
        if not matched:
            raise ValueError(f"Source column '{self.source_col}' not found.")
        series = df_out[matched[0]]

        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        alpha = 1.0 / self.period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        # Handle division by zero where avg_loss was 0
        rsi = rsi.fillna(100.0)

        df_out[f"RSI_{self.period}"] = rsi
        return df_out


class MACDIndicator(BaseIndicator):
    """
    Moving Average Convergence Divergence (MACD).
    Calculates MACD Line, Signal Line, and MACD Histogram.
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, source_col: str = "close"):
        super().__init__(
            name="MACD",
            params={"fast": fast, "slow": slow, "signal": signal, "source_col": source_col},
        )
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.source_col = source_col

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        col = self.source_col.lower()
        matched = [c for c in df_out.columns if c.lower() == col]
        if not matched:
            raise ValueError(f"Source column '{self.source_col}' not found.")
        series = df_out[matched[0]]

        fast_ema = series.ewm(span=self.fast, adjust=False).mean()
        slow_ema = series.ewm(span=self.slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
        hist = macd_line - signal_line

        df_out[f"MACD_{self.fast}_{self.slow}_{self.signal}"] = macd_line
        df_out[f"MACD_SIGNAL_{self.fast}_{self.slow}_{self.signal}"] = signal_line
        df_out[f"MACD_HIST_{self.fast}_{self.slow}_{self.signal}"] = hist

        # Generic column aliases for ease of access
        df_out["MACD"] = macd_line
        df_out["MACD_SIGNAL"] = signal_line
        df_out["MACD_HIST"] = hist

        return df_out


class StochasticRSIIndicator(BaseIndicator):
    """
    Stochastic RSI.
    Applies the Stochastic oscillator formula to RSI values.
    Returns %K and %D lines.
    """

    def __init__(
        self,
        period: int = 14,
        rsi_period: int = 14,
        k_period: int = 3,
        d_period: int = 3,
        source_col: str = "close",
    ):
        super().__init__(
            name="STOCH_RSI",
            params={
                "period": period,
                "rsi_period": rsi_period,
                "k_period": k_period,
                "d_period": d_period,
                "source_col": source_col,
            },
        )
        self.period = period
        self.rsi_period = rsi_period
        self.k_period = k_period
        self.d_period = d_period
        self.source_col = source_col

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        rsi_col = f"RSI_{self.rsi_period}"
        if rsi_col not in df.columns:
            df_out = RSIIndicator(period=self.rsi_period, source_col=self.source_col).calculate(df)
        else:
            df_out = df.copy()

        rsi = df_out[rsi_col]
        min_rsi = rsi.rolling(window=self.period, min_periods=self.period).min()
        max_rsi = rsi.rolling(window=self.period, min_periods=self.period).max()

        denom = max_rsi - min_rsi
        stoch_rsi = (rsi - min_rsi) / denom.replace(0, np.nan)
        stoch_rsi = stoch_rsi.fillna(0.5)

        k = (stoch_rsi.rolling(window=self.k_period, min_periods=1).mean()) * 100.0
        d = k.rolling(window=self.d_period, min_periods=1).mean()

        df_out[f"STOCH_RSI_K_{self.period}_{self.k_period}"] = k
        df_out[f"STOCH_RSI_D_{self.period}_{self.d_period}"] = d
        df_out["STOCH_RSI_K"] = k
        df_out["STOCH_RSI_D"] = d

        return df_out


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Convenience function to compute RSI."""
    return RSIIndicator(period=period).calculate(df)


def calculate_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """Convenience function to compute MACD."""
    return MACDIndicator(fast=fast, slow=slow, signal=signal).calculate(df)


def calculate_stoch_rsi(
    df: pd.DataFrame, period: int = 14, rsi_period: int = 14, k: int = 3, d: int = 3
) -> pd.DataFrame:
    """Convenience function to compute Stochastic RSI."""
    return StochasticRSIIndicator(
        period=period, rsi_period=rsi_period, k_period=k, d_period=d
    ).calculate(df)
