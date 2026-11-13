"""
EMA Crossover Strategy.
Identifies trend transitions and momentum shifts via fast and slow exponential moving average crossovers.
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.trend import EMAIndicator
from app.indicators.volatility import ATRIndicator
from app.strategies.base import BaseStrategy, StrategyResult


class EMACrossoverStrategy(BaseStrategy):
    """
    EMA Crossover Strategy.
    
    Generates signals when the fast EMA crosses the slow EMA:
    - BUY: Fast EMA crosses above Slow EMA
    - SELL: Fast EMA crosses below Slow EMA
    - Filter: Requires crossover on the most recently completed/current candle
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.H1,
        fast_period: int = 9,
        slow_period: int = 21,
        atr_multiplier: float = 1.5,
        risk_reward_ratio: float = 2.0,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        params.setdefault("fast_period", fast_period)
        params.setdefault("slow_period", slow_period)
        params.setdefault("atr_multiplier", atr_multiplier)
        params.setdefault("risk_reward_ratio", risk_reward_ratio)

        super().__init__(
            name="EMACrossover",
            symbol=symbol,
            timeframe=timeframe,
            parameters=params,
        )
        self.fast_period = int(self.parameters["fast_period"])
        self.slow_period = int(self.parameters["slow_period"])
        self.atr_multiplier = float(self.parameters["atr_multiplier"])
        self.risk_reward_ratio = float(self.parameters["risk_reward_ratio"])

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        if df.empty or len(df) < max(self.slow_period, 20) + 2:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning="Insufficient candle history for EMA calculation.",
            )

        fast_col = f"EMA_{self.fast_period}"
        slow_col = f"EMA_{self.slow_period}"

        df_calc = df.copy()
        if fast_col not in df_calc.columns or slow_col not in df_calc.columns:
            df_calc = EMAIndicator(periods=[self.fast_period, self.slow_period]).calculate(df_calc)
        if "ATR" not in df_calc.columns and "ATR_14" not in df_calc.columns:
            df_calc = ATRIndicator(period=14).calculate(df_calc)

        curr = df_calc.iloc[-1]
        prev = df_calc.iloc[-2]

        close = float(curr["close"])
        curr_fast = float(curr[fast_col])
        curr_slow = float(curr[slow_col])
        prev_fast = float(prev[fast_col])
        prev_slow = float(prev[slow_col])
        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        indicators_used = {
            "close": close,
            "fast_ema": curr_fast,
            "slow_ema": curr_slow,
            "prev_fast_ema": prev_fast,
            "prev_slow_ema": prev_slow,
            "atr": round(atr, 5),
        }

        # Crossover logic
        bullish_crossover = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
        bearish_crossover = (prev_fast >= prev_slow) and (curr_fast < curr_slow)

        if bullish_crossover:
            confidence = 0.75
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bullish EMA crossover on {self.symbol}: Fast EMA({self.fast_period}) [{curr_fast:.5f}] "
                f"crossed above Slow EMA({self.slow_period}) [{curr_slow:.5f}]."
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

        if bearish_crossover:
            confidence = 0.75
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bearish EMA crossover on {self.symbol}: Fast EMA({self.fast_period}) [{curr_fast:.5f}] "
                f"crossed below Slow EMA({self.slow_period}) [{curr_slow:.5f}]."
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

        # In-trend continuation or neutral
        trend_status = "Bullish" if curr_fast > curr_slow else "Bearish"
        spread = abs(curr_fast - curr_slow)
        return StrategyResult(
            strategy_name=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal=SignalType.HOLD,
            confidence=0.0,
            reasoning=f"No crossover detected. Current state: {trend_status} (EMA separation: {spread:.5f}).",
            indicators_used=indicators_used,
            entry_price=close,
        )
