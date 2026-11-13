"""
Bollinger Bands Strategy.
Combines volatility envelope boundaries (2 standard deviations) with RSI momentum
exhaustion to catch counter-trend bounces back to the mean.
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.momentum import RSIIndicator
from app.indicators.volatility import ATRIndicator, BollingerBandsIndicator
from app.strategies.base import BaseStrategy, StrategyResult


class BollingerBandsStrategy(BaseStrategy):
    """
    Bollinger Bands Mean Reversion Strategy with RSI Confirmation.

    Rules:
    - BUY: Low/Close touches or penetrates Lower Band AND RSI <= rsi_oversold (e.g. 35)
      Take Profit target: Middle Band (SMA 20)
    - SELL: High/Close touches or penetrates Upper Band AND RSI >= rsi_overbought (e.g. 65)
      Take Profit target: Middle Band (SMA 20)
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.M30,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 65.0,
        atr_multiplier: float = 1.5,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        params.setdefault("bb_period", bb_period)
        params.setdefault("bb_std", bb_std)
        params.setdefault("rsi_period", rsi_period)
        params.setdefault("rsi_oversold", rsi_oversold)
        params.setdefault("rsi_overbought", rsi_overbought)
        params.setdefault("atr_multiplier", atr_multiplier)

        super().__init__(
            name="BollingerBands",
            symbol=symbol,
            timeframe=timeframe,
            parameters=params,
        )
        self.bb_period = int(self.parameters["bb_period"])
        self.bb_std = float(self.parameters["bb_std"])
        self.rsi_period = int(self.parameters["rsi_period"])
        self.rsi_oversold = float(self.parameters["rsi_oversold"])
        self.rsi_overbought = float(self.parameters["rsi_overbought"])
        self.atr_multiplier = float(self.parameters["atr_multiplier"])

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        if df.empty or len(df) < max(self.bb_period, self.rsi_period) + 2:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning="Insufficient candle history for Bollinger Bands.",
            )

        df_calc = df.copy()
        if "BB_LOWER" not in df_calc.columns or "BB_UPPER" not in df_calc.columns:
            df_calc = BollingerBandsIndicator(period=self.bb_period, std_dev=self.bb_std).calculate(df_calc)
        rsi_col = f"RSI_{self.rsi_period}"
        if rsi_col not in df_calc.columns and "RSI" not in df_calc.columns:
            df_calc = RSIIndicator(period=self.rsi_period).calculate(df_calc)
        if "ATR" not in df_calc.columns and "ATR_14" not in df_calc.columns:
            df_calc = ATRIndicator(period=14).calculate(df_calc)

        curr = df_calc.iloc[-1]
        close = float(curr["close"])
        low = float(curr.get("low", close))
        high = float(curr.get("high", close))
        bb_upper = float(curr["BB_UPPER"])
        bb_middle = float(curr["BB_MIDDLE"])
        bb_lower = float(curr["BB_LOWER"])
        rsi = float(curr.get(rsi_col, curr.get("RSI", 50.0)))
        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        digits = symbol_info.get("digits", 5) if symbol_info else 5

        indicators_used = {
            "close": close,
            "bb_upper": round(bb_upper, digits),
            "bb_middle": round(bb_middle, digits),
            "bb_lower": round(bb_lower, digits),
            "rsi": round(rsi, 2),
            "atr": round(atr, digits),
        }

        # Long: Price touching or below lower band, RSI oversold
        if low <= bb_lower and rsi <= self.rsi_oversold:
            confidence = min(0.85, 0.65 + ((self.rsi_oversold - rsi) / 50.0))
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            # TP targeted at middle band
            tp = round(bb_middle, digits)
            if tp <= close:  # Fallback if close already surpassed middle
                tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, 1.5, self.atr_multiplier)

            reasoning = (
                f"Bollinger Band Lower Touch on {self.symbol}: Low ({low:.5f}) touched lower band ({bb_lower:.5f}) "
                f"with oversold RSI ({rsi:.1f} <= {self.rsi_oversold:.1f}). Target: Middle band ({bb_middle:.5f})."
            )
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.BUY,
                confidence=round(confidence, 2),
                reasoning=reasoning,
                indicators_used=indicators_used,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            )

        # Short: Price touching or above upper band, RSI overbought
        if high >= bb_upper and rsi >= self.rsi_overbought:
            confidence = min(0.85, 0.65 + ((rsi - self.rsi_overbought) / 50.0))
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = round(bb_middle, digits)
            if tp >= close:
                tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, 1.5, self.atr_multiplier)

            reasoning = (
                f"Bollinger Band Upper Touch on {self.symbol}: High ({high:.5f}) touched upper band ({bb_upper:.5f}) "
                f"with overbought RSI ({rsi:.1f} >= {self.rsi_overbought:.1f}). Target: Middle band ({bb_middle:.5f})."
            )
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.SELL,
                confidence=round(confidence, 2),
                reasoning=reasoning,
                indicators_used=indicators_used,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            )

        return StrategyResult(
            strategy_name=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal=SignalType.HOLD,
            confidence=0.0,
            reasoning=f"Price within bands [{bb_lower:.5f} - {bb_upper:.5f}], RSI={rsi:.1f}.",
            indicators_used=indicators_used,
            entry_price=close,
        )
