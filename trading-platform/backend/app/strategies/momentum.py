"""
Momentum Strategy.
Synergizes RSI, Stochastic RSI, and MACD to capture high-velocity directional breakouts
where momentum oscillators are strongly synchronized.
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.calculator import IndicatorCalculator
from app.strategies.base import BaseStrategy, StrategyResult


class MomentumStrategy(BaseStrategy):
    """
    Multi-Oscillator Momentum Strategy.
    
    Bullish Alignment:
    - RSI > 50 (momentum favors buyers)
    - Stochastic RSI %K > %D and %K > 20 (not in deep oversold, moving up)
    - MACD Histogram > 0 and expanding
    
    Bearish Alignment:
    - RSI < 50 (momentum favors sellers)
    - Stochastic RSI %K < %D and %K < 80 (not in deep overbought, moving down)
    - MACD Histogram < 0 and declining
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.M15,
        atr_multiplier: float = 1.5,
        risk_reward_ratio: float = 2.0,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        params.setdefault("atr_multiplier", atr_multiplier)
        params.setdefault("risk_reward_ratio", risk_reward_ratio)

        super().__init__(
            name="MomentumStrategy",
            symbol=symbol,
            timeframe=timeframe,
            parameters=params,
        )
        self.atr_multiplier = float(self.parameters["atr_multiplier"])
        self.risk_reward_ratio = float(self.parameters["risk_reward_ratio"])

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        if df.empty or len(df) < 35:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning="Insufficient candle history for Momentum Strategy.",
            )

        needed = ["RSI_14", "STOCH_RSI_K", "STOCH_RSI_D", "MACD_HIST", "ATR"]
        if not all(c in df.columns for c in needed):
            calc = IndicatorCalculator()
            df_calc = calc.calculate_all(df)
        else:
            df_calc = df

        curr = df_calc.iloc[-1]
        prev = df_calc.iloc[-2]

        close = float(curr["close"])
        rsi = float(curr.get("RSI_14", curr.get("RSI", 50.0)))
        stoch_k = float(curr["STOCH_RSI_K"])
        stoch_d = float(curr["STOCH_RSI_D"])
        prev_stoch_k = float(prev["STOCH_RSI_K"])
        prev_stoch_d = float(prev["STOCH_RSI_D"])
        macd_hist = float(curr["MACD_HIST"])
        prev_macd_hist = float(prev["MACD_HIST"])
        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        indicators_used = {
            "close": close,
            "rsi": round(rsi, 2),
            "stoch_k": round(stoch_k, 2),
            "stoch_d": round(stoch_d, 2),
            "macd_hist": round(macd_hist, 6),
            "prev_macd_hist": round(prev_macd_hist, 6),
            "atr": round(atr, 5),
        }

        # Bullish conditions
        bullish_rsi = 52.0 <= rsi <= 72.0
        bullish_stoch = (stoch_k > stoch_d) and (stoch_k >= prev_stoch_k) and (stoch_k < 85.0)
        bullish_macd = macd_hist > 0 and macd_hist >= prev_macd_hist

        # Bearish conditions
        bearish_rsi = 28.0 <= rsi <= 48.0
        bearish_stoch = (stoch_k < stoch_d) and (stoch_k <= prev_stoch_k) and (stoch_k > 15.0)
        bearish_macd = macd_hist < 0 and macd_hist <= prev_macd_hist

        if bullish_rsi and bullish_stoch and bullish_macd:
            confidence = 0.85
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Triple Momentum Bullish Alignment on {self.symbol}: "
                f"RSI={rsi:.1f} in bullish expansion zone, StochRSI %K ({stoch_k:.1f}) > %D ({stoch_d:.1f}), "
                f"and MACD Hist ({macd_hist:.6f}) expanding positive."
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

        if bearish_rsi and bearish_stoch and bearish_macd:
            confidence = 0.85
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Triple Momentum Bearish Alignment on {self.symbol}: "
                f"RSI={rsi:.1f} in bearish acceleration zone, StochRSI %K ({stoch_k:.1f}) < %D ({stoch_d:.1f}), "
                f"and MACD Hist ({macd_hist:.6f}) expanding negative."
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
            reasoning="Momentum oscillators are divergent or lacking synchronized agreement.",
            indicators_used=indicators_used,
            entry_price=close,
        )
