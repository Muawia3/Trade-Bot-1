"""
Multi-Indicator Consensus Strategy.
Weighted voting matrix evaluating Trend, Momentum, Volatility, and Volume indicators.
Enforces a consensus threshold before generating actionable trade signals.
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.calculator import IndicatorCalculator
from app.strategies.base import BaseStrategy, StrategyResult


class MultiIndicatorStrategy(BaseStrategy):
    """
    Multi-Indicator Strategy.
    
    Assigns normalized weights to individual indicator sub-components:
    - Trend (EMA20/50/200 & ADX): Weight 0.35
    - Momentum (RSI & MACD): Weight 0.30
    - Volatility (Bollinger Bands): Weight 0.20
    - Volume (VWAP & Volume SMA): Weight 0.15
    
    A signal is only produced if the aggregated score exceeds consensus_threshold (default 0.65).
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.H1,
        consensus_threshold: float = 0.65,
        weights: Optional[Dict[str, float]] = None,
        atr_multiplier: float = 1.75,
        risk_reward_ratio: float = 2.0,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        default_weights = {
            "trend": 0.35,
            "momentum": 0.30,
            "volatility": 0.20,
            "volume": 0.15,
        }
        if weights:
            default_weights.update(weights)

        params.setdefault("consensus_threshold", consensus_threshold)
        params.setdefault("weights", default_weights)
        params.setdefault("atr_multiplier", atr_multiplier)
        params.setdefault("risk_reward_ratio", risk_reward_ratio)

        super().__init__(
            name="MultiIndicatorConsensus",
            symbol=symbol,
            timeframe=timeframe,
            parameters=params,
        )
        self.consensus_threshold = float(self.parameters["consensus_threshold"])
        self.weights = self.parameters["weights"]
        self.atr_multiplier = float(self.parameters["atr_multiplier"])
        self.risk_reward_ratio = float(self.parameters["risk_reward_ratio"])

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        if df.empty or len(df) < 50:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning="Insufficient candle history for Multi-Indicator Consensus.",
            )

        calc = IndicatorCalculator()
        df_calc = calc.calculate_all(df)
        curr = df_calc.iloc[-1]
        prev = df_calc.iloc[-2]

        close = float(curr["close"])
        ema20 = float(curr["EMA_20"])
        ema50 = float(curr["EMA_50"])
        ema200 = float(curr["EMA_200"])
        adx = float(curr.get("ADX_14", 0.0))
        plus_di = float(curr.get("PLUS_DI_14", 0.0))
        minus_di = float(curr.get("MINUS_DI_14", 0.0))
        rsi = float(curr.get("RSI_14", 50.0))
        macd = float(curr.get("MACD", 0.0))
        macd_signal = float(curr.get("MACD_SIGNAL", 0.0))
        bb_upper = float(curr.get("BB_UPPER", close))
        bb_middle = float(curr.get("BB_MIDDLE", close))
        bb_lower = float(curr.get("BB_LOWER", close))
        vwap = float(curr.get("VWAP", close))
        vol_sma = float(curr.get("VOL_SMA", 1.0))
        volume = float(curr.get("volume", curr.get("tick_volume", 1.0)))
        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        # 1. Trend component (-1.0 to +1.0)
        trend_score = 0.0
        if close > ema20 > ema50 > ema200:
            trend_score = 1.0 if (adx > 25 and plus_di > minus_di) else 0.7
        elif close < ema20 < ema50 < ema200:
            trend_score = -1.0 if (adx > 25 and minus_di > plus_di) else -0.7
        elif ema20 > ema50:
            trend_score = 0.4
        elif ema20 < ema50:
            trend_score = -0.4

        # 2. Momentum component (-1.0 to +1.0)
        momentum_score = 0.0
        # RSI contribution
        if rsi > 55:
            momentum_score += 0.5
        elif rsi < 45:
            momentum_score -= 0.5

        # MACD contribution
        if macd > macd_signal:
            momentum_score += 0.5
        elif macd < macd_signal:
            momentum_score -= 0.5

        # 3. Volatility component (-1.0 to +1.0)
        vol_score = 0.0
        if close < bb_lower:
            vol_score = 0.8  # Oversold bounce potential
        elif close > bb_upper:
            vol_score = -0.8  # Overbought pullback potential
        elif close > bb_middle:
            vol_score = 0.3
        else:
            vol_score = -0.3

        # 4. Volume component (-1.0 to +1.0)
        volume_score = 0.0
        if close > vwap and volume >= vol_sma:
            volume_score = 1.0
        elif close > vwap:
            volume_score = 0.5
        elif close < vwap and volume >= vol_sma:
            volume_score = -1.0
        elif close < vwap:
            volume_score = -0.5

        # Aggregate weighted score
        w_trend = self.weights.get("trend", 0.35)
        w_mom = self.weights.get("momentum", 0.30)
        w_vol = self.weights.get("volatility", 0.20)
        w_volu = self.weights.get("volume", 0.15)
        total_weight = w_trend + w_mom + w_vol + w_volu

        composite_score = (
            (trend_score * w_trend)
            + (momentum_score * w_mom)
            + (vol_score * w_vol)
            + (volume_score * w_volu)
        ) / total_weight

        indicators_used = {
            "close": close,
            "composite_score": round(composite_score, 3),
            "trend_score": round(trend_score, 2),
            "momentum_score": round(momentum_score, 2),
            "volatility_score": round(vol_score, 2),
            "volume_score": round(volume_score, 2),
            "rsi": round(rsi, 2),
            "macd": round(macd, 6),
            "vwap": round(vwap, 5),
            "atr": round(atr, 5),
        }

        # Check against consensus threshold
        if composite_score >= self.consensus_threshold:
            confidence = min(0.95, 0.60 + (composite_score * 0.35))
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Multi-Indicator Consensus BUY on {self.symbol} (Score: {composite_score:.2f} >= {self.consensus_threshold:.2f}). "
                f"Breakdown: Trend={trend_score:.2f}, Mom={momentum_score:.2f}, Vol={vol_score:.2f}, Volume={volume_score:.2f}."
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

        if composite_score <= -self.consensus_threshold:
            confidence = min(0.95, 0.60 + (abs(composite_score) * 0.35))
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Multi-Indicator Consensus SELL on {self.symbol} (Score: {composite_score:.2f} <= -{self.consensus_threshold:.2f}). "
                f"Breakdown: Trend={trend_score:.2f}, Mom={momentum_score:.2f}, Vol={vol_score:.2f}, Volume={volume_score:.2f}."
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
            reasoning=(
                f"Consensus score ({composite_score:.2f}) inside neutral band "
                f"[-{self.consensus_threshold:.2f}, +{self.consensus_threshold:.2f}]."
            ),
            indicators_used=indicators_used,
            entry_price=close,
        )
