"""
MACD Confirmation Strategy.
Captures momentum expansion by pairing MACD line / signal line crossovers
with histogram direction confirmation.
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.momentum import MACDIndicator
from app.indicators.volatility import ATRIndicator
from app.strategies.base import BaseStrategy, StrategyResult


class MACDConfirmationStrategy(BaseStrategy):
    """
    MACD Confirmation Strategy.
    
    Entry:
    - BUY: MACD Line crosses above Signal Line AND Histogram is positive and expanding.
    - SELL: MACD Line crosses below Signal Line AND Histogram is negative and expanding.
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.H1,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        atr_multiplier: float = 1.6,
        risk_reward_ratio: float = 2.0,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        params.setdefault("fast_period", fast_period)
        params.setdefault("slow_period", slow_period)
        params.setdefault("signal_period", signal_period)
        params.setdefault("atr_multiplier", atr_multiplier)
        params.setdefault("risk_reward_ratio", risk_reward_ratio)

        super().__init__(
            name="MACDConfirmation",
            symbol=symbol,
            timeframe=timeframe,
            parameters=params,
        )
        self.fast_period = int(self.parameters["fast_period"])
        self.slow_period = int(self.parameters["slow_period"])
        self.signal_period = int(self.parameters["signal_period"])
        self.atr_multiplier = float(self.parameters["atr_multiplier"])
        self.risk_reward_ratio = float(self.parameters["risk_reward_ratio"])

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        if df.empty or len(df) < self.slow_period + self.signal_period + 5:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning="Insufficient candle history for MACD calculation.",
            )

        df_calc = df.copy()
        if "MACD" not in df_calc.columns or "MACD_SIGNAL" not in df_calc.columns:
            df_calc = MACDIndicator(
                fast=self.fast_period, slow=self.slow_period, signal=self.signal_period
            ).calculate(df_calc)
        if "ATR" not in df_calc.columns and "ATR_14" not in df_calc.columns:
            df_calc = ATRIndicator(period=14).calculate(df_calc)

        curr = df_calc.iloc[-1]
        prev = df_calc.iloc[-2]

        close = float(curr["close"])
        macd_curr = float(curr["MACD"])
        signal_curr = float(curr["MACD_SIGNAL"])
        hist_curr = float(curr["MACD_HIST"])

        macd_prev = float(prev["MACD"])
        signal_prev = float(prev["MACD_SIGNAL"])
        hist_prev = float(prev["MACD_HIST"])

        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        indicators_used = {
            "close": close,
            "macd": round(macd_curr, 6),
            "signal": round(signal_curr, 6),
            "hist": round(hist_curr, 6),
            "prev_macd": round(macd_prev, 6),
            "prev_signal": round(signal_prev, 6),
            "prev_hist": round(hist_prev, 6),
            "atr": round(atr, 5),
        }

        # Crossover checks
        bullish_cross = (macd_prev <= signal_prev) and (macd_curr > signal_curr)
        bullish_hist_conf = hist_curr > 0 and hist_curr >= hist_prev

        bearish_cross = (macd_prev >= signal_prev) and (macd_curr < signal_curr)
        bearish_hist_conf = hist_curr < 0 and hist_curr <= hist_prev

        if bullish_cross and bullish_hist_conf:
            confidence = 0.80
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bullish MACD crossover on {self.symbol}: MACD line ({macd_curr:.6f}) crossed above "
                f"signal ({signal_curr:.6f}) with expanding positive histogram ({hist_curr:.6f} > {hist_prev:.6f})."
            )
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.BUY,
                confidence=confidence,
                reasoning=reasoning,
                indicators_used=indicators_used,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            )

        if bearish_cross and bearish_hist_conf:
            confidence = 0.80
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bearish MACD crossover on {self.symbol}: MACD line ({macd_curr:.6f}) crossed below "
                f"signal ({signal_curr:.6f}) with expanding negative histogram ({hist_curr:.6f} < {hist_prev:.6f})."
            )
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.SELL,
                confidence=confidence,
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
            reasoning=f"No MACD crossover setup. Current MACD: {macd_curr:.6f}, Signal: {signal_curr:.6f}, Hist: {hist_curr:.6f}.",
            indicators_used=indicators_used,
            entry_price=close,
        )
