"""
AI Prediction Service for advisory market direction forecasting.

Integrates feature extraction, model inference, and hybrid signal synthesis.
Guarantees that AI predictions remain strictly ADVISORY and never bypass
systemic risk controls or trade sizing parameters.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from app.ai.feature_engineering import FeatureEngineer
from app.ai.model_manager import ModelManager, PredictionOutput
from app.core.config import get_settings
from app.core.constants import SignalType
from app.core.logging_config import get_logger

logger = get_logger("app.ai.prediction_service")


@dataclass
class AIPrediction:
    """Dataclass holding an AI model prediction output with advisory notes."""
    symbol: str
    timeframe: str
    direction: str  # "BUY", "SELL", "NEUTRAL"
    confidence: float
    probabilities: Dict[str, float]
    model_name: str
    model_type: str
    reasoning: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_advisory: bool = True
    risk_warning: str = (
        "AI prediction is probabilistic and advisory only. "
        "It must NEVER bypass stop losses, risk limits, or money management rules."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert prediction to dictionary."""
        return asdict(self)


@dataclass
class MergedSignal:
    """Composite signal combining rule-based strategy and AI advisory inference."""
    symbol: str
    strategy_signal: str  # "buy", "sell", "hold"
    ai_direction: str     # "BUY", "SELL", "NEUTRAL"
    final_action: str     # "BUY", "SELL", "HOLD"
    confidence: float
    alignment: str        # "CONFIRMED", "CONTRADICTED", "NEUTRAL", "STANDALONE"
    rationale: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    risk_advisory_confirmed: bool = True


class PredictionService:
    """
    High-level service providing AI directional analysis for trading strategies.

    Manages feature extraction, model lookup, advisory signal merging, and accuracy tracking.
    """

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        feature_engineer: Optional[FeatureEngineer] = None,
    ) -> None:
        """
        Initialize the PredictionService.

        Args:
            model_manager: ModelManager instance or auto-created.
            feature_engineer: FeatureEngineer instance or auto-created.
        """
        self.settings = get_settings()
        self.model_manager = model_manager or ModelManager()
        self.feature_engineer = feature_engineer or FeatureEngineer()

        # Track prediction outcomes over time for calibration
        self._prediction_history: List[Dict[str, Any]] = []

    def get_prediction(
        self,
        symbol: str,
        timeframe: str,
        market_data: Optional[pd.DataFrame] = None,
        model_name: Optional[str] = None,
    ) -> Optional[AIPrediction]:
        """
        Generate directional prediction for a given symbol and timeframe.

        Args:
            symbol: Financial instrument (e.g., 'XAUUSD', 'EURUSD').
            timeframe: Candle timeframe string ('M15', 'H1', etc.).
            market_data: OHLCV DataFrame. Must have at least 30 candles if provided.
            model_name: Specific registered model to use (or latest active).

        Returns:
            AIPrediction object or None if AI is disabled or data is insufficient.
        """
        if not self.settings.AI_ENABLED:
            logger.debug("AI predictions are disabled in configuration (AI_ENABLED=false).")
            return None

        # Resolve model name
        target_model = model_name or self.model_manager.get_active_model_for(symbol, timeframe)
        if not target_model:
            logger.info("No active model registered for %s on timeframe %s", symbol, timeframe)
            return None

        if market_data is None or len(market_data) < 25:
            logger.warning(
                "Insufficient market data for %s (%d bars). Need >= 25 bars.",
                symbol,
                len(market_data) if market_data is not None else 0,
            )
            return None

        try:
            # 1. Extract and normalize features
            raw_features = self.feature_engineer.extract_features(market_data, include_labels=False)
            if raw_features.empty:
                logger.warning("Feature extraction yielded empty dataframe for %s", symbol)
                return None

            latest_features = raw_features.iloc[[-1]]

            # 2. Query model manager for inference
            output: PredictionOutput = self.model_manager.predict(target_model, latest_features)

            # 3. Formulate reasoning notes
            reasoning = [
                f"Model '{target_model}' inferred {output.direction} with {output.confidence:.1%} confidence",
                f"Probabilities: Down={output.probabilities[0]:.2f}, Up={output.probabilities[1] if len(output.probabilities) > 1 else 0.0:.2f}",
                f"RSI-14: {raw_features['rsi_14'].iloc[-1]:.1f}, MACD-Hist: {raw_features['macd_hist'].iloc[-1]:.5f}",
                f"ATR-14 Ratio: {raw_features['atr_ratio'].iloc[-1]:.4f}",
            ]

            prediction = AIPrediction(
                symbol=symbol,
                timeframe=timeframe,
                direction=output.direction,
                confidence=output.confidence,
                probabilities={
                    "down": output.probabilities[0],
                    "up": output.probabilities[1] if len(output.probabilities) > 1 else 0.0,
                },
                model_name=target_model,
                model_type=str(output.metadata.get("model_type", "ml")),
                reasoning=reasoning,
            )

            # Log prediction history
            self._prediction_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": output.direction,
                "confidence": output.confidence,
                "close_price": float(market_data["close"].iloc[-1]),
                "realized_return": None,
            })

            return prediction

        except Exception as exc:
            logger.error("Error generating AI prediction for %s: %s", symbol, exc, exc_info=True)
            return None

    def merge_with_strategy_signal(
        self,
        symbol: str,
        strategy_signal: str,
        ai_prediction: Optional[AIPrediction],
        min_ai_confidence: float = 0.60,
    ) -> MergedSignal:
        """
        Synthesize technical strategy signal with AI advisory stance.

        Rules of engagement:
        - Strategy signal is the PRIMARY catalyst.
        - AI is an ADVISORY filter/booster.
        - If strategy is HOLD, AI never forces an entry.
        - If strategy and AI align with high confidence (> min_ai_confidence), signal is CONFIRMED with boosted weight.
        - If AI strongly contradicts the strategy, final action is tempered to HOLD or lower confidence to protect capital.
        - If AI is unavailable or low confidence, strategy signal passes as STANDALONE.

        Args:
            symbol: Financial instrument.
            strategy_signal: 'buy', 'sell', or 'hold' from strategy.
            ai_prediction: Optional AIPrediction instance.
            min_ai_confidence: Confidence threshold required for AI confirmation.

        Returns:
            MergedSignal with clear rationale.
        """
        strat = strategy_signal.lower().strip()

        # If no AI prediction available, passthrough strategy signal
        if ai_prediction is None:
            return MergedSignal(
                symbol=symbol,
                strategy_signal=strat,
                ai_direction="NEUTRAL",
                final_action=strat.upper(),
                confidence=0.5,
                alignment="STANDALONE",
                rationale="AI advisory not active. Pure strategy signal executed.",
            )

        ai_dir = ai_prediction.direction.upper()
        ai_conf = ai_prediction.confidence

        # Case 1: Strategy has no signal (HOLD)
        if strat in ("hold", "neutral", "none"):
            return MergedSignal(
                symbol=symbol,
                strategy_signal=strat,
                ai_direction=ai_dir,
                final_action="HOLD",
                confidence=0.0,
                alignment="NEUTRAL",
                rationale=f"Strategy is in HOLD. AI indicates {ai_dir} ({ai_conf:.1%}), but AI cannot initiate trades alone.",
            )

        # Case 2: Strategy BUY
        if strat == "buy":
            if ai_dir == "BUY" and ai_conf >= min_ai_confidence:
                return MergedSignal(
                    symbol=symbol,
                    strategy_signal=strat,
                    ai_direction=ai_dir,
                    final_action="BUY",
                    confidence=min(ai_conf + 0.15, 0.95),
                    alignment="CONFIRMED",
                    rationale=f"Strategy BUY strongly confirmed by AI model {ai_prediction.model_name} ({ai_conf:.1%}).",
                )
            elif ai_dir == "SELL" and ai_conf >= min_ai_confidence:
                # Contradiction: Filter out trade to protect capital
                return MergedSignal(
                    symbol=symbol,
                    strategy_signal=strat,
                    ai_direction=ai_dir,
                    final_action="HOLD",
                    confidence=0.3,
                    alignment="CONTRADICTED",
                    rationale=f"Strategy BUY rejected: AI model strongly indicates SELL ({ai_conf:.1%}). Trade filtered.",
                )
            else:
                return MergedSignal(
                    symbol=symbol,
                    strategy_signal=strat,
                    ai_direction=ai_dir,
                    final_action="BUY",
                    confidence=0.55,
                    alignment="NEUTRAL",
                    rationale=f"Strategy BUY accepted with standard confidence (AI stance {ai_dir} is neutral/low confidence).",
                )

        # Case 3: Strategy SELL
        if strat == "sell":
            if ai_dir == "SELL" and ai_conf >= min_ai_confidence:
                return MergedSignal(
                    symbol=symbol,
                    strategy_signal=strat,
                    ai_direction=ai_dir,
                    final_action="SELL",
                    confidence=min(ai_conf + 0.15, 0.95),
                    alignment="CONFIRMED",
                    rationale=f"Strategy SELL strongly confirmed by AI model {ai_prediction.model_name} ({ai_conf:.1%}).",
                )
            elif ai_dir == "BUY" and ai_conf >= min_ai_confidence:
                # Contradiction: Filter trade
                return MergedSignal(
                    symbol=symbol,
                    strategy_signal=strat,
                    ai_direction=ai_dir,
                    final_action="HOLD",
                    confidence=0.3,
                    alignment="CONTRADICTED",
                    rationale=f"Strategy SELL rejected: AI model strongly indicates BUY ({ai_conf:.1%}). Trade filtered.",
                )
            else:
                return MergedSignal(
                    symbol=symbol,
                    strategy_signal=strat,
                    ai_direction=ai_dir,
                    final_action="SELL",
                    confidence=0.55,
                    alignment="NEUTRAL",
                    rationale=f"Strategy SELL accepted with standard confidence (AI stance {ai_dir} is neutral/low confidence).",
                )

        return MergedSignal(
            symbol=symbol,
            strategy_signal=strat,
            ai_direction=ai_dir,
            final_action="HOLD",
            confidence=0.0,
            alignment="NEUTRAL",
            rationale="Unrecognized strategy signal type.",
        )

    def record_actual_outcome(self, symbol: str, actual_direction: str, return_pct: float) -> None:
        """Update live prediction logs with actual observed market outcomes to track accuracy."""
        for record in reversed(self._prediction_history):
            if record["symbol"] == symbol and record["realized_return"] is None:
                record["realized_return"] = return_pct
                record["actual_direction"] = actual_direction
                record["was_correct"] = bool(
                    (record["direction"] == "BUY" and return_pct > 0)
                    or (record["direction"] == "SELL" and return_pct < 0)
                )
                break

    def get_accuracy_stats(self) -> Dict[str, Any]:
        """Compute rolling historical accuracy statistics for AI predictions."""
        evaluated = [r for r in self._prediction_history if r.get("was_correct") is not None]
        if not evaluated:
            return {"total_predictions": len(self._prediction_history), "evaluated": 0, "accuracy": None}

        correct_count = sum(1 for r in evaluated if r["was_correct"])
        return {
            "total_predictions": len(self._prediction_history),
            "evaluated": len(evaluated),
            "correct": correct_count,
            "accuracy": float(correct_count / len(evaluated)),
        }
