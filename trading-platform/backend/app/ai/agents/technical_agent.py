"""
Technical Analysis Agent.

Conducts multi-indicator technical analysis across price action, momentum,
trend confluence, and volatility envelopes to yield technical stances.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.ai.agents.base_agent import AgentRecommendation, AgentResult, AnalysisAgent
from app.core.logging_config import get_logger

logger = get_logger("app.ai.agents.technical_agent")


class TechnicalAgent(AnalysisAgent):
    """
    Evaluates algorithmic indicator confluence:
    - Moving Average stacks (EMA 9, 21, 50, 200)
    - Momentum oscillators (RSI, MACD)
    - Volatility envelopes (Bollinger Bands %B and Bandwidth)
    """

    def __init__(self, name: str = "TechnicalAgent") -> None:
        super().__init__(
            name=name,
            description="Analyzes indicator confluence across momentum, moving averages, and volatility bands.",
        )

    def analyze(
        self,
        market_data: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Compute indicator indicators and formulate a technical recommendation.

        Args:
            market_data: OHLCV DataFrame.
            context: Optional execution parameters.

        Returns:
            AgentResult with technical score, indicator values, and reasoning.
        """
        if market_data.empty or len(market_data) < 25:
            return AgentResult(
                agent_name=self.name,
                recommendation=AgentRecommendation.HOLD,
                confidence=0.0,
                findings={},
                reasoning=["Insufficient data points to compute full technical indicator suite."],
            )

        df = market_data.copy()
        df.columns = [str(c).lower().strip() for c in df.columns]
        close = df["close"]

        # 1. EMAs
        ema_9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
        ema_21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        ema_50 = close.ewm(span=min(50, len(close)), adjust=False).mean().iloc[-1]
        latest_close = close.iloc[-1]

        # 2. RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_series = 100.0 - (100.0 / (1.0 + rs))
        latest_rsi = float(rsi_series.iloc[-1])

        # 3. MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        curr_macd_line = float(macd_line.iloc[-1])
        curr_macd_sig = float(macd_signal.iloc[-1])
        curr_macd_hist = float(macd_hist.iloc[-1])
        prev_macd_hist = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else curr_macd_hist

        # 4. Bollinger Bands (20, 2)
        bb_mid = close.rolling(window=20).mean()
        bb_std = close.rolling(window=20).std()
        bb_upper = bb_mid + 2.0 * bb_std
        bb_lower = bb_mid - 2.0 * bb_std
        band_diff = bb_upper.iloc[-1] - bb_lower.iloc[-1]
        pct_b = float((latest_close - bb_lower.iloc[-1]) / band_diff) if band_diff > 0 else 0.5

        # ---------------------------------------------------------------------
        # Confluence Scoring Engine
        # Positive score -> Bullish, Negative score -> Bearish
        # ---------------------------------------------------------------------
        bullish_signals = 0
        bearish_signals = 0
        reasoning: List[str] = []

        # EMA Trend alignment
        if latest_close > ema_9 > ema_21 > ema_50:
            bullish_signals += 2
            reasoning.append("Bullish EMA alignment: Close > EMA9 > EMA21 > EMA50.")
        elif latest_close < ema_9 < ema_21 < ema_50:
            bearish_signals += 2
            reasoning.append("Bearish EMA alignment: Close < EMA9 < EMA21 < EMA50.")
        elif latest_close > ema_21:
            bullish_signals += 1
            reasoning.append("Price trading above short-term baseline EMA21.")
        else:
            bearish_signals += 1
            reasoning.append("Price trading below short-term baseline EMA21.")

        # RSI Momentum
        if 50.0 < latest_rsi < 68.0:
            bullish_signals += 1
            reasoning.append(f"RSI ({latest_rsi:.1f}) in constructive bullish expansion zone.")
        elif 32.0 < latest_rsi < 50.0:
            bearish_signals += 1
            reasoning.append(f"RSI ({latest_rsi:.1f}) in constructive bearish expansion zone.")
        elif latest_rsi >= 70.0:
            bearish_signals += 1
            reasoning.append(f"RSI ({latest_rsi:.1f}) is Overbought (exhaustion risk).")
        elif latest_rsi <= 30.0:
            bullish_signals += 1
            reasoning.append(f"RSI ({latest_rsi:.1f}) is Oversold (mean reversion potential).")

        # MACD Histogram momentum
        if curr_macd_hist > 0 and curr_macd_hist > prev_macd_hist:
            bullish_signals += 1
            reasoning.append(f"MACD histogram positive and accelerating ({curr_macd_hist:.5f}).")
        elif curr_macd_hist < 0 and curr_macd_hist < prev_macd_hist:
            bearish_signals += 1
            reasoning.append(f"MACD histogram negative and decelerating ({curr_macd_hist:.5f}).")

        # Bollinger position
        if pct_b < 0.15:
            reasoning.append(f"Price testing lower Bollinger Band (%B: {pct_b:.2f}).")
        elif pct_b > 0.85:
            reasoning.append(f"Price testing upper Bollinger Band (%B: {pct_b:.2f}).")

        # Synthesis
        total_signals = bullish_signals + bearish_signals
        if bullish_signals > bearish_signals and bullish_signals >= 2:
            rec = AgentRecommendation.BUY
            confidence = min(0.55 + (bullish_signals - bearish_signals) * 0.1, 0.90)
        elif bearish_signals > bullish_signals and bearish_signals >= 2:
            rec = AgentRecommendation.SELL
            confidence = min(0.55 + (bearish_signals - bullish_signals) * 0.1, 0.90)
        else:
            rec = AgentRecommendation.HOLD
            confidence = 0.50
            reasoning.append("Indicator signals are mixed or neutral; holding stance.")

        findings = {
            "close": round(float(latest_close), 5),
            "ema_9": round(float(ema_9), 5),
            "ema_21": round(float(ema_21), 5),
            "ema_50": round(float(ema_50), 5),
            "rsi_14": round(float(latest_rsi), 2),
            "macd_line": round(float(curr_macd_line), 5),
            "macd_signal": round(float(curr_macd_sig), 5),
            "macd_hist": round(float(curr_macd_hist), 5),
            "bb_pct_b": round(float(pct_b), 3),
            "bullish_points": bullish_signals,
            "bearish_points": bearish_signals,
        }

        return AgentResult(
            agent_name=self.name,
            recommendation=rec,
            confidence=round(confidence, 2),
            findings=findings,
            reasoning=reasoning,
        )
