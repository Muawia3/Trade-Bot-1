"""
Trend Following Strategy.
Uses multi-timeframe EMA alignment (EMA20, EMA50, EMA200) filtered by ADX trend strength.
Features dedicated parameter profiles for Forex (EURUSD) and Gold (XAUUSD).
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.calculator import IndicatorCalculator
from app.strategies.base import BaseStrategy, StrategyResult


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy based on EMA cascade and ADX momentum filter.
    
    Rules:
    - Bullish: Close > EMA20 > EMA50 > EMA200 AND ADX > adx_threshold AND +DI > -DI
    - Bearish: Close < EMA20 < EMA50 < EMA200 AND ADX > adx_threshold AND -DI > +DI
    - Exit / Neutral: ADX drops below adx_exit_threshold or price crosses EMA50 against trend
    """

    DEFAULT_PROFILES = {
        "XAUUSD": {
            "adx_threshold": 28.0,
            "adx_exit_threshold": 20.0,
            "atr_multiplier": 2.2,
            "risk_reward_ratio": 2.2,
            "timeframe": TimeFrame.H1,
        },
        "EURUSD": {
            "adx_threshold": 25.0,
            "adx_exit_threshold": 18.0,
            "atr_multiplier": 1.5,
            "risk_reward_ratio": 2.0,
            "timeframe": TimeFrame.H1,
        },
    }

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.H1,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        symbol_clean = symbol.upper()
        profile = self.DEFAULT_PROFILES.get(
            symbol_clean,
            self.DEFAULT_PROFILES.get("EURUSD", {}),
        ).copy()

        if parameters:
            profile.update(parameters)

        super().__init__(
            name="TrendFollowing",
            symbol=symbol_clean,
            timeframe=timeframe,
            parameters=profile,
        )
        self.adx_threshold = float(self.parameters.get("adx_threshold", 25.0))
        self.adx_exit_threshold = float(self.parameters.get("adx_exit_threshold", 18.0))
        self.atr_multiplier = float(self.parameters.get("atr_multiplier", 1.5))
        self.risk_reward_ratio = float(self.parameters.get("risk_reward_ratio", 2.0))

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        if df.empty or len(df) < 50:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning="Insufficient candle history for EMA200 and ADX calculation.",
            )

        # Ensure indicators exist
        needed_cols = ["EMA_20", "EMA_50", "EMA_200", "ADX_14", "PLUS_DI_14", "MINUS_DI_14", "ATR_14"]
        if not all(c in df.columns for c in needed_cols):
            calc = IndicatorCalculator()
            df = calc.calculate_all(df)

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        close = float(curr["close"])
        ema20 = float(curr["EMA_20"])
        ema50 = float(curr["EMA_50"])
        ema200 = float(curr["EMA_200"])
        adx = float(curr.get("ADX_14", curr.get("ADX", 0.0)))
        plus_di = float(curr.get("PLUS_DI_14", 0.0))
        minus_di = float(curr.get("MINUS_DI_14", 0.0))
        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        indicators_used = {
            "close": close,
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "adx": round(adx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "atr": round(atr, 5),
        }

        # Check Bullish alignment
        bullish_alignment = close > ema20 > ema50 > ema200
        strong_bullish_adx = adx >= self.adx_threshold and plus_di > minus_di

        # Check Bearish alignment
        bearish_alignment = close < ema20 < ema50 < ema200
        strong_bearish_adx = adx >= self.adx_threshold and minus_di > plus_di

        # Confidence calculation based on ADX level and EMA spacing
        adx_factor = min(1.0, max(0.0, (adx - self.adx_threshold) / 25.0))

        if bullish_alignment and strong_bullish_adx:
            confidence = min(0.95, 0.65 + (0.30 * adx_factor))
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bullish trend confirmed on {self.symbol}: Price ({close:.5f}) > EMA20 ({ema20:.5f}) "
                f"> EMA50 ({ema50:.5f}) > EMA200 ({ema200:.5f}). "
                f"ADX={adx:.1f} (>= {self.adx_threshold:.1f}) with +DI ({plus_di:.1f}) > -DI ({minus_di:.1f})."
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

        if bearish_alignment and strong_bearish_adx:
            confidence = min(0.95, 0.65 + (0.30 * adx_factor))
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bearish trend confirmed on {self.symbol}: Price ({close:.5f}) < EMA20 ({ema20:.5f}) "
                f"< EMA50 ({ema50:.5f}) < EMA200 ({ema200:.5f}). "
                f"ADX={adx:.1f} (>= {self.adx_threshold:.1f}) with -DI ({minus_di:.1f}) > +DI ({plus_di:.1f})."
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

        # Neutral / Hold
        reasons = []
        if not (bullish_alignment or bearish_alignment):
            reasons.append("EMAs not in full directional hierarchy")
        if adx < self.adx_threshold:
            reasons.append(f"ADX ({adx:.1f}) below strength threshold ({self.adx_threshold:.1f})")

        return StrategyResult(
            strategy_name=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal=SignalType.HOLD,
            confidence=0.0,
            reasoning="Market consolidating or choppy: " + "; ".join(reasons),
            indicators_used=indicators_used,
            entry_price=close,
        )
