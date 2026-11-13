"""
Market Analysis Agent.

Diagnoses overarching market conditions:
- Market Regime: Strong Trend (Up/Down), Weak Trend, Range-Bound / Consolidation, Volatile Expansion
- Volatility Level: Low, Normal, High, Extreme
- Liquidity / Active Session alignment
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.ai.agents.base_agent import AgentRecommendation, AgentResult, AnalysisAgent
from app.core.logging_config import get_logger

logger = get_logger("app.ai.agents.market_analysis_agent")


class MarketRegime(str, Enum):
    """Classification of macro price behavior."""
    STRONG_UPTREND = "STRONG_UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    RANGING_CONSOLIDATION = "RANGING_CONSOLIDATION"
    WEAK_DOWNTREND = "WEAK_DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    HIGH_VOLATILITY_EXPANSION = "HIGH_VOLATILITY_EXPANSION"


class MarketAnalysisAgent(AnalysisAgent):
    """
    Evaluates global market structure, regime, and session dynamics.

    Provides contextual framework for technical strategies and execution timing.
    """

    def __init__(self, name: str = "MarketAnalysisAgent") -> None:
        super().__init__(
            name=name,
            description="Assesses market regime, trend persistence, volatility state, and session dynamics.",
        )

    def analyze(
        self,
        market_data: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Analyze price action history to detect regime and broad directional bias.

        Args:
            market_data: OHLCV DataFrame. Must have at least 30 rows.
            context: Optional contextual parameters (e.g. current symbol, current session).

        Returns:
            AgentResult containing regime diagnosis and bias.
        """
        if market_data.empty or len(market_data) < 20:
            return AgentResult(
                agent_name=self.name,
                recommendation=AgentRecommendation.HOLD,
                confidence=0.0,
                findings={"regime": "INSUFFICIENT_DATA"},
                reasoning=["Insufficient data points (< 20 bars) to characterize market regime."],
            )

        df = market_data.copy()
        df.columns = [str(c).lower().strip() for c in df.columns]
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # 1. Trend Analysis via Moving Averages
        sma_20 = close.rolling(window=20).mean()
        sma_50 = close.rolling(window=min(50, len(close))).mean()
        latest_close = close.iloc[-1]
        latest_sma20 = sma_20.iloc[-1]
        latest_sma50 = sma_50.iloc[-1]

        # ADX / Directional Momentum approximation
        tr = np.maximum(high - low, np.maximum((high - close.shift(1)).abs(), (low - close.shift(1)).abs()))
        atr_14 = tr.rolling(window=14).mean().iloc[-1]
        atr_ratio = atr_14 / latest_close if latest_close > 0 else 0.0

        # Linear regression slope over last 20 bars to gauge velocity
        x_vals = np.arange(min(20, len(close)))
        y_vals = close.iloc[-len(x_vals):].values
        slope = np.polyfit(x_vals, y_vals, 1)[0]
        normalized_slope = (slope / latest_close) * 1000.0  # Normalized slope in per-mille

        # 2. Determine Volatility State
        recent_vol = close.pct_change().iloc[-20:].std() * np.sqrt(252)
        if atr_ratio > 0.015:
            vol_state = "EXTREME"
        elif atr_ratio > 0.007:
            vol_state = "HIGH"
        elif atr_ratio < 0.002:
            vol_state = "LOW"
        else:
            vol_state = "NORMAL"

        # 3. Classify Market Regime
        reasoning: List[str] = []

        if vol_state == "EXTREME":
            regime = MarketRegime.HIGH_VOLATILITY_EXPANSION
            rec = AgentRecommendation.HOLD
            confidence = 0.4
            reasoning.append(f"Market is in high-volatility expansion (ATR ratio: {atr_ratio:.4f}). High risk of whipsaws.")
        elif latest_close > latest_sma20 > latest_sma50 and normalized_slope > 0.5:
            regime = MarketRegime.STRONG_UPTREND
            rec = AgentRecommendation.BUY
            confidence = min(0.65 + min(normalized_slope * 0.05, 0.25), 0.90)
            reasoning.append(f"Strong uptrend confirmed: Price > SMA20 > SMA50 with positive slope ({normalized_slope:.2f}).")
        elif latest_close > latest_sma20:
            regime = MarketRegime.WEAK_UPTREND
            rec = AgentRecommendation.BUY
            confidence = 0.60
            reasoning.append("Moderate upward bias: Price trading above SMA20.")
        elif latest_close < latest_sma20 < latest_sma50 and normalized_slope < -0.5:
            regime = MarketRegime.STRONG_DOWNTREND
            rec = AgentRecommendation.SELL
            confidence = min(0.65 + min(abs(normalized_slope) * 0.05, 0.25), 0.90)
            reasoning.append(f"Strong downtrend confirmed: Price < SMA20 < SMA50 with negative slope ({normalized_slope:.2f}).")
        elif latest_close < latest_sma20:
            regime = MarketRegime.WEAK_DOWNTREND
            rec = AgentRecommendation.SELL
            confidence = 0.60
            reasoning.append("Moderate downward bias: Price trading below SMA20.")
        else:
            regime = MarketRegime.RANGING_CONSOLIDATION
            rec = AgentRecommendation.HOLD
            confidence = 0.50
            reasoning.append("Market is range-bound / consolidating. Trend-following strategies should exercise caution.")

        findings = {
            "regime": regime.value,
            "volatility_state": vol_state,
            "normalized_slope": round(float(normalized_slope), 3),
            "atr_14": round(float(atr_14), 5),
            "atr_ratio": round(float(atr_ratio), 5),
            "latest_close": round(float(latest_close), 5),
            "sma_20": round(float(latest_sma20), 5),
            "sma_50": round(float(latest_sma50), 5),
        }

        return AgentResult(
            agent_name=self.name,
            recommendation=rec,
            confidence=round(confidence, 2),
            findings=findings,
            reasoning=reasoning,
        )
