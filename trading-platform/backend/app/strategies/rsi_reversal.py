"""
RSI Reversal Strategy.
Trades mean-reversion pullbacks in overbought and oversold market extremes,
confirmed by candlestick direction and a macro trend filter.
"""

from typing import Any, Dict, Optional, Union
import pandas as pd

from app.core.constants import SignalType, TimeFrame
from app.indicators.momentum import RSIIndicator
from app.indicators.trend import EMAIndicator
from app.indicators.volatility import ATRIndicator
from app.strategies.base import BaseStrategy, StrategyResult


class RSIReversalStrategy(BaseStrategy):
    """
    RSI Mean Reversion Strategy with Trend Filter.
    
    Entry Conditions:
    - BUY: RSI < oversold_threshold (30) AND Bullish Candle (close > open) 
           AND (optional) Close > EMA200 for pullback in bull trend
    - SELL: RSI > overbought_threshold (70) AND Bearish Candle (close < open)
           AND (optional) Close < EMA200 for pullback in bear trend
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.M15,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        use_trend_filter: bool = True,
        trend_ema_period: int = 200,
        atr_multiplier: float = 1.5,
        risk_reward_ratio: float = 1.8,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        params.setdefault("rsi_period", rsi_period)
        params.setdefault("oversold", oversold)
        params.setdefault("overbought", overbought)
        params.setdefault("use_trend_filter", use_trend_filter)
        params.setdefault("trend_ema_period", trend_ema_period)
        params.setdefault("atr_multiplier", atr_multiplier)
        params.setdefault("risk_reward_ratio", risk_reward_ratio)

        super().__init__(
            name="RSIReversal",
            symbol=symbol,
            timeframe=timeframe,
            parameters=params,
        )
        self.rsi_period = int(self.parameters["rsi_period"])
        self.oversold = float(self.parameters["oversold"])
        self.overbought = float(self.parameters["overbought"])
        self.use_trend_filter = bool(self.parameters["use_trend_filter"])
        self.trend_ema_period = int(self.parameters["trend_ema_period"])
        self.atr_multiplier = float(self.parameters["atr_multiplier"])
        self.risk_reward_ratio = float(self.parameters["risk_reward_ratio"])

    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        min_candles = self.trend_ema_period if self.use_trend_filter else (self.rsi_period + 5)
        if df.empty or len(df) < min_candles:
            return StrategyResult(
                strategy_name=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal=SignalType.HOLD,
                confidence=0.0,
                reasoning=f"Insufficient candles ({len(df)} < {min_candles}) for RSI Reversal.",
            )

        df_calc = df.copy()
        rsi_col = f"RSI_{self.rsi_period}"
        ema_col = f"EMA_{self.trend_ema_period}"

        if rsi_col not in df_calc.columns:
            df_calc = RSIIndicator(period=self.rsi_period).calculate(df_calc)
        if self.use_trend_filter and ema_col not in df_calc.columns:
            df_calc = EMAIndicator(periods=[self.trend_ema_period]).calculate(df_calc)
        if "ATR" not in df_calc.columns and "ATR_14" not in df_calc.columns:
            df_calc = ATRIndicator(period=14).calculate(df_calc)

        curr = df_calc.iloc[-1]
        prev = df_calc.iloc[-2]

        close = float(curr["close"])
        open_p = float(curr["open"])
        curr_rsi = float(curr[rsi_col])
        prev_rsi = float(prev[rsi_col])
        trend_ema = float(curr[ema_col]) if self.use_trend_filter else close
        atr = float(curr.get("ATR_14", curr.get("ATR", 0.0)))

        is_bullish_candle = close > open_p
        is_bearish_candle = close < open_p

        indicators_used = {
            "close": close,
            "open": open_p,
            "rsi": round(curr_rsi, 2),
            "prev_rsi": round(prev_rsi, 2),
            "trend_ema": round(trend_ema, 5),
            "atr": round(atr, 5),
        }

        # Long: RSI is turning up from oversold + Bullish candle
        # If trend filter is on, price should be above trend EMA (buying dips in uptrend)
        # or RSI extreme oversold (< 25)
        bullish_reversal = (prev_rsi <= self.oversold or curr_rsi <= self.oversold) and is_bullish_candle
        if self.use_trend_filter:
            trend_ok_buy = (close >= trend_ema) or (curr_rsi < self.oversold - 5.0)
        else:
            trend_ok_buy = True

        if bullish_reversal and trend_ok_buy:
            confidence = min(0.90, 0.65 + ((self.oversold - min(curr_rsi, prev_rsi)) / 100.0) * 0.5)
            sl = self.get_stop_loss(close, SignalType.BUY, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.BUY, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bullish RSI Reversal on {self.symbol}: RSI reached oversold ({curr_rsi:.1f} <= {self.oversold:.1f}) "
                f"with confirming green candle (Close {close:.5f} > Open {open_p:.5f}). "
                f"Trend filter EMA({self.trend_ema_period}) at {trend_ema:.5f}."
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

        # Short: RSI is turning down from overbought + Bearish candle
        bearish_reversal = (prev_rsi >= self.overbought or curr_rsi >= self.overbought) and is_bearish_candle
        if self.use_trend_filter:
            trend_ok_sell = (close <= trend_ema) or (curr_rsi > self.overbought + 5.0)
        else:
            trend_ok_sell = True

        if bearish_reversal and trend_ok_sell:
            confidence = min(0.90, 0.65 + ((max(curr_rsi, prev_rsi) - self.overbought) / 100.0) * 0.5)
            sl = self.get_stop_loss(close, SignalType.SELL, atr, symbol_info, self.atr_multiplier)
            tp = self.get_take_profit(close, SignalType.SELL, atr, symbol_info, self.risk_reward_ratio, self.atr_multiplier)
            reasoning = (
                f"Bearish RSI Reversal on {self.symbol}: RSI reached overbought ({curr_rsi:.1f} >= {self.overbought:.1f}) "
                f"with confirming red candle (Close {close:.5f} < Open {open_p:.5f}). "
                f"Trend filter EMA({self.trend_ema_period}) at {trend_ema:.5f}."
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
            reasoning=f"RSI in neutral zone ({curr_rsi:.1f}). Overbought={self.overbought:.1f}, Oversold={self.oversold:.1f}.",
            indicators_used=indicators_used,
            entry_price=close,
        )
