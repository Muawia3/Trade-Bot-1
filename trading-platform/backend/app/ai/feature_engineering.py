"""
Feature Engineering module for Financial Time-Series Market Data.

Generates price action, technical indicator, volatility, cyclic temporal,
and lagged features tailored for machine learning models predicting Forex and Gold market dynamics.

All calculations handle edge cases, missing data, and prevent lookahead bias.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler

from app.core.constants import TRADING_SESSION_HOURS, TradingSession
from app.core.logging_config import get_logger

logger = get_logger("app.ai.feature_engineering")


class FeatureEngineer:
    """
    Extracts, normalizes, and manages feature sets for Forex & Gold machine learning models.

    Ensures no future data leakage by strictly using rolling window operations and backward shifts.
    """

    def __init__(
        self,
        scaler_type: str = "robust",
        fill_method: str = "ffill_zero",
        ema_periods: Tuple[int, ...] = (9, 21, 50, 200),
        momentum_periods: Tuple[int, ...] = (3, 5, 10, 20),
        lag_periods: int = 5,
    ) -> None:
        """
        Initialize the FeatureEngineer.

        Args:
            scaler_type: 'robust' (RobustScaler) or 'standard' (StandardScaler).
            fill_method: Method to handle initial NaNs from rolling/diff calculations ('ffill_zero', 'drop').
            ema_periods: EMA spans for distance calculation.
            momentum_periods: Lookbacks for momentum and acceleration.
            lag_periods: Number of lag return steps to construct.
        """
        self.scaler_type = scaler_type.lower()
        self.fill_method = fill_method
        self.ema_periods = ema_periods
        self.momentum_periods = momentum_periods
        self.lag_periods = lag_periods

        self.scaler: Optional[Union[StandardScaler, RobustScaler]] = None
        self._feature_names: List[str] = []
        self._is_fitted: bool = False

    @property
    def is_fitted(self) -> bool:
        """Return whether the internal feature scaler has been fitted."""
        return self._is_fitted

    def get_feature_names(self) -> List[str]:
        """Return the list of extracted feature column names."""
        return list(self._feature_names)

    def extract_features(
        self,
        df: pd.DataFrame,
        include_labels: bool = False,
        forward_horizon: int = 1,
        return_threshold: float = 0.0002,
    ) -> pd.DataFrame:
        """
        Extract financial, statistical, and indicator features from OHLCV DataFrame.

        Args:
            df: DataFrame containing at least ['open', 'high', 'low', 'close'] and optional ['volume'/'tick_volume'].
                Index can be DatetimeIndex or a column 'time'/'timestamp' must be present.
            include_labels: If True, computes target classification label 'target_direction'
                            (-1 for down, 0 for neutral, 1 for up or binary 0/1 depending on use).
            forward_horizon: Future bars to look ahead for label calculation (only when include_labels=True).
            return_threshold: Minimum absolute forward return to trigger directional signal instead of flat.

        Returns:
            DataFrame containing calculated features (and target if requested).
        """
        if df.empty:
            logger.warning("Empty DataFrame provided to extract_features")
            return pd.DataFrame()

        data = df.copy()

        # Standardize column names to lowercase
        data.columns = [str(c).lower().strip() for c in data.columns]

        # Ensure required OHLC columns exist
        required_cols = ["open", "high", "low", "close"]
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Required column '{col}' missing from DataFrame")

        # Cast OHLC to float64
        for col in required_cols:
            data[col] = data[col].astype(np.float64)

        if "volume" not in data.columns:
            if "tick_volume" in data.columns:
                data["volume"] = data["tick_volume"].astype(np.float64)
            else:
                data["volume"] = 1.0  # default dummy volume if unavailable

        features = pd.DataFrame(index=data.index)

        # ---------------------------------------------------------------------
        # 1. Price-based features
        # ---------------------------------------------------------------------
        close = data["close"]
        high = data["high"]
        low = data["low"]
        open_ = data["open"]

        # Simple returns & Log returns
        features["return_1"] = close.pct_change(1)
        features["log_return_1"] = np.log(close / close.shift(1).replace(0, np.nan))

        # Price Momentum (Rate of Change)
        for p in self.momentum_periods:
            features[f"momentum_{p}"] = (close - close.shift(p)) / close.shift(p).replace(0, np.nan)

        # Price Acceleration (Change in momentum)
        features["price_acceleration_5"] = features["momentum_5"] - features["momentum_5"].shift(1)
        features["price_acceleration_10"] = features["momentum_10"] - features["momentum_10"].shift(1)

        # Intraday spreads / range ratios
        features["hl_spread"] = (high - low) / close.replace(0, np.nan)
        features["co_spread"] = (close - open_) / close.replace(0, np.nan)
        features["upper_shadow"] = (high - np.maximum(close, open_)) / close.replace(0, np.nan)
        features["lower_shadow"] = (np.minimum(close, open_) - low) / close.replace(0, np.nan)

        # ---------------------------------------------------------------------
        # 2. Indicator-based features
        # ---------------------------------------------------------------------
        # Relative Strength Index (RSI 14)
        features["rsi_14"] = self._compute_rsi(close, period=14)

        # Moving Average Convergence Divergence (MACD: 12, 26, 9)
        macd_line, macd_signal, macd_hist = self._compute_macd(close, fast=12, slow=26, signal=9)
        features["macd_line"] = macd_line
        features["macd_signal"] = macd_signal
        features["macd_hist"] = macd_hist

        # Exponential Moving Average distances
        for period in self.ema_periods:
            ema_val = close.ewm(span=period, adjust=False).mean()
            features[f"ema_{period}_dist"] = (close - ema_val) / ema_val.replace(0, np.nan)

        # Bollinger Bands (20 periods, 2 std)
        bb_pos, bb_width = self._compute_bollinger_bands(close, period=20, std_dev=2.0)
        features["bb_position"] = bb_pos      # %B: 0 = lower band, 1 = upper band
        features["bb_width"] = bb_width        # Bandwidth relative to middle band

        # ---------------------------------------------------------------------
        # 3. Volatility features
        # ---------------------------------------------------------------------
        # Average True Range (ATR 14) normalized by close price
        atr_14 = self._compute_atr(high, low, close, period=14)
        features["atr_14"] = atr_14
        features["atr_ratio"] = atr_14 / close.replace(0, np.nan)

        # Realized Volatility (rolling std of log returns over 10 and 20 periods)
        log_ret = features["log_return_1"]
        features["realized_vol_10"] = log_ret.rolling(window=10).std()
        features["realized_vol_20"] = log_ret.rolling(window=20).std()

        # Garman-Klass Volatility:
        # 0.5 * (ln(H/L))^2 - (2*ln(2) - 1) * (ln(C/O))^2
        hl_term = np.log(high / low.replace(0, np.nan)) ** 2
        co_term = np.log(close / open_.replace(0, np.nan)) ** 2
        gk_instant = 0.5 * hl_term - (2 * np.log(2) - 1.0) * co_term
        # Smooth with a 10-period rolling mean
        features["garman_klass_vol"] = np.sqrt(np.maximum(gk_instant.rolling(window=10).mean(), 0.0))

        # ---------------------------------------------------------------------
        # 4. Temporal & Session Features (Cyclic sin/cos encoding)
        # ---------------------------------------------------------------------
        timestamps = self._resolve_timestamps(data)
        if timestamps is not None:
            hours = timestamps.dt.hour + timestamps.dt.minute / 60.0
            day_of_week = timestamps.dt.dayofweek

            # Cyclic hour of day (24-hour cycle)
            features["hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
            features["hour_cos"] = np.cos(2 * np.pi * hours / 24.0)

            # Cyclic day of week (7-day cycle)
            features["dow_sin"] = np.sin(2 * np.pi * day_of_week / 7.0)
            features["dow_cos"] = np.cos(2 * np.pi * day_of_week / 7.0)

            # Trading sessions (binary indicators)
            features["session_asian"] = self._in_session(hours, TradingSession.ASIAN)
            features["session_london"] = self._in_session(hours, TradingSession.LONDON)
            features["session_ny"] = self._in_session(hours, TradingSession.NEW_YORK)
            features["session_overlap"] = self._in_session(hours, TradingSession.OVERLAP)
        else:
            # Fallback zero temporal features if no timestamp index or column found
            features["hour_sin"] = 0.0
            features["hour_cos"] = 0.0
            features["dow_sin"] = 0.0
            features["dow_cos"] = 0.0
            features["session_asian"] = 0.0
            features["session_london"] = 0.0
            features["session_ny"] = 0.0
            features["session_overlap"] = 0.0

        # ---------------------------------------------------------------------
        # 5. Lag Features
        # ---------------------------------------------------------------------
        for lag in range(1, self.lag_periods + 1):
            features[f"return_lag_{lag}"] = features["return_1"].shift(lag)

        features["rsi_lag_1"] = features["rsi_14"].shift(1)
        features["rsi_lag_2"] = features["rsi_14"].shift(2)
        features["macd_hist_lag_1"] = features["macd_hist"].shift(1)
        features["macd_hist_lag_2"] = features["macd_hist"].shift(2)

        # ---------------------------------------------------------------------
        # 6. Optional Target Calculation (Forward return classification)
        # ---------------------------------------------------------------------
        if include_labels:
            forward_return = close.shift(-forward_horizon) / close - 1.0
            # 1: Long/Up, 0: Down/Short (binary classification target)
            features["target_direction"] = (forward_return > return_threshold).astype(int)
            # Continuous forward return for regression or custom multi-class
            features["target_return"] = forward_return

        # ---------------------------------------------------------------------
        # Clean infinities and NaNs
        # ---------------------------------------------------------------------
        features = features.replace([np.inf, -np.inf], np.nan)

        if self.fill_method == "ffill_zero":
            features = features.ffill().fillna(0.0)
        elif self.fill_method == "drop":
            features = features.dropna()

        # Update feature names list (excluding targets)
        feature_cols = [c for c in features.columns if not c.startswith("target_")]
        self._feature_names = feature_cols

        return features

    def fit_scaler(self, features: pd.DataFrame) -> FeatureEngineer:
        """
        Fit the internal scaler on training features.

        Args:
            features: Feature DataFrame.

        Returns:
            self
        """
        cols = [c for c in features.columns if not c.startswith("target_")]
        if not cols:
            raise ValueError("No feature columns available to fit scaler")

        if self.scaler_type == "robust":
            self.scaler = RobustScaler()
        else:
            self.scaler = StandardScaler()

        self.scaler.fit(features[cols])
        self._is_fitted = True
        self._feature_names = cols
        logger.info("Fitted %s on %d features over %d samples", self.scaler_type, len(cols), len(features))
        return self

    def normalize_features(
        self,
        features: pd.DataFrame,
        fit: bool = False,
    ) -> pd.DataFrame:
        """
        Scale features using fitted or newly fit scaler while preserving column names and index.

        Args:
            features: DataFrame containing raw feature columns.
            fit: If True, fits scaler on this dataset before transforming.

        Returns:
            Normalized DataFrame with identical column names and index.
        """
        if features.empty:
            return features.copy()

        cols = [c for c in features.columns if not c.startswith("target_")]

        if fit or not self._is_fitted or self.scaler is None:
            self.fit_scaler(features[cols])

        transformed_vals = self.scaler.transform(features[cols])
        scaled_df = pd.DataFrame(transformed_vals, index=features.index, columns=cols)

        # Re-attach target columns untouched if present
        target_cols = [c for c in features.columns if c.startswith("target_")]
        for tc in target_cols:
            scaled_df[tc] = features[tc]

        return scaled_df

    # -------------------------------------------------------------------------
    # Helper Computations
    # -------------------------------------------------------------------------

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Wilder's Relative Strength Index calculation."""
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def _compute_macd(
        series: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Compute standard MACD line, signal line, and histogram."""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def _compute_bollinger_bands(
        series: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[pd.Series, pd.Series]:
        """Compute Bollinger Bands %B and Bandwidth."""
        rolling_mean = series.rolling(window=period).mean()
        rolling_std = series.rolling(window=period).std()

        upper = rolling_mean + std_dev * rolling_std
        lower = rolling_mean - std_dev * rolling_std
        band_diff = upper - lower

        # %B: position of close relative to bands
        pct_b = (series - lower) / band_diff.replace(0, np.nan)
        # Bandwidth: relative width to mean
        bandwidth = band_diff / rolling_mean.replace(0, np.nan)

        return pct_b.fillna(0.5), bandwidth.fillna(0.0)

    @staticmethod
    def _compute_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """Compute Average True Range (ATR)."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        return atr.fillna(0.0)

    @staticmethod
    def _resolve_timestamps(df: pd.DataFrame) -> Optional[pd.Series]:
        """Attempt to resolve timestamp series from index or datetime columns."""
        if isinstance(df.index, pd.DatetimeIndex):
            return pd.Series(df.index, index=df.index)

        for col in ["time", "timestamp", "datetime", "date"]:
            if col in df.columns:
                try:
                    return pd.to_datetime(df[col])
                except Exception:
                    pass

        return None

    @staticmethod
    def _in_session(hours_series: pd.Series, session: TradingSession) -> pd.Series:
        """Check if fractional hour falls within session UTC range."""
        start, end = TRADING_SESSION_HOURS[session]
        if start <= end:
            return ((hours_series >= start) & (hours_series < end)).astype(float)
        else:
            # Over midnight wrap-around
            return ((hours_series >= start) | (hours_series < end)).astype(float)
