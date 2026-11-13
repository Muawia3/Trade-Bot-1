"""
Signal Generator module.
Evaluates strategies against live/historical market data, formats comprehensive
explanations, and produces weighted consensus signals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from app.core.constants import SignalType
from app.core.logging_config import get_logger
from app.schemas.signal import SignalCreate
from app.strategies.base import BaseStrategy, StrategyResult

logger = get_logger("signals.generator")


@dataclass
class Signal:
    """Internal Signal representation used across Strategy, Risk, and Execution engines."""
    symbol: str
    signal_type: SignalType
    strategy_name: str
    timeframe: str
    confidence: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str = ""
    indicators_snapshot: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expired_at: Optional[datetime] = None

    @property
    def is_actionable(self) -> bool:
        """True if signal is BUY or SELL."""
        return self.signal_type in (SignalType.BUY, SignalType.SELL)

    def to_schema(self) -> SignalCreate:
        """Converts to Pydantic schema for persistence and API responses."""
        return SignalCreate(
            symbol=self.symbol,
            signal_type=self.signal_type.value.upper(),
            strategy_name=self.strategy_name,
            timeframe=self.timeframe,
            confidence=self.confidence,
            entry_price=self.entry_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            indicators_snapshot=self.indicators_snapshot,
            reasoning=self.reasoning,
            expired_at=self.expired_at,
        )


class SignalGenerator:
    """
    Coordinates signal generation across strategies, builds explainability reports,
    and calculates multi-strategy consensus aggregations.
    """

    def __init__(self, signal_validity_minutes: int = 60):
        self.signal_validity_minutes = signal_validity_minutes

    def generate_signals(
        self,
        symbol: str,
        market_data: pd.DataFrame,
        strategies: List[BaseStrategy],
        symbol_info: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        """
        Runs the provided strategies on market data for a symbol and returns generated Signals.
        """
        signals: List[Signal] = []
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=self.signal_validity_minutes)

        for strategy in strategies:
            if not strategy.enabled:
                continue

            try:
                res: StrategyResult = strategy.analyze(market_data, symbol_info=symbol_info)
                if not strategy.validate_signal(res):
                    logger.debug("Strategy %s signal failed validation: %s", strategy.name, res.reasoning)
                    continue

                if res.is_actionable and res.entry_price is not None:
                    signal = Signal(
                        symbol=symbol.upper(),
                        signal_type=res.signal,
                        strategy_name=strategy.name,
                        timeframe=strategy.timeframe,
                        confidence=res.confidence,
                        entry_price=res.entry_price,
                        stop_loss=res.stop_loss,
                        take_profit=res.take_profit,
                        reasoning=self.format_signal_reasoning(res),
                        indicators_snapshot=res.indicators_used,
                        timestamp=now,
                        expired_at=expiry,
                    )
                    signals.append(signal)

            except Exception as e:
                logger.error(
                    "Error generating signal from %s on %s: %s",
                    strategy.name,
                    symbol,
                    str(e),
                    exc_info=True,
                )

        return signals

    def aggregate_signals(
        self,
        signals: List[Signal],
        min_consensus_confidence: float = 0.65,
    ) -> Optional[Signal]:
        """
        Aggregates multiple strategy signals for the same symbol into a unified consensus signal.
        Filters out conflicting signals and calculates a weighted average entry, SL, and TP.
        """
        if not signals:
            return None

        # Filter for actionable signals on the same symbol
        actionable = [s for s in signals if s.is_actionable]
        if not actionable:
            return None

        symbol = actionable[0].symbol
        buy_signals = [s for s in actionable if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in actionable if s.signal_type == SignalType.SELL]

        buy_weight = sum(s.confidence for s in buy_signals)
        sell_weight = sum(s.confidence for s in sell_signals)

        total_weight = buy_weight + sell_weight
        if total_weight == 0:
            return None

        # Detect conflict
        if buy_weight > 0 and sell_weight > 0:
            conflict_ratio = min(buy_weight, sell_weight) / max(buy_weight, sell_weight)
            if conflict_ratio > 0.40:
                logger.info(
                    "Signal conflict for %s: BUY weight=%.2f vs SELL weight=%.2f (ratio=%.2f). No consensus.",
                    symbol,
                    buy_weight,
                    sell_weight,
                    conflict_ratio,
                )
                return None

        # Determine winning side
        if buy_weight > sell_weight:
            winning_signals = buy_signals
            winning_side = SignalType.BUY
            consensus_conf = buy_weight / len(signals)
        else:
            winning_signals = sell_signals
            winning_side = SignalType.SELL
            consensus_conf = sell_weight / len(signals)

        # Consensus confidence normalization
        avg_confidence = sum(s.confidence for s in winning_signals) / len(winning_signals)
        # Bonus for multi-strategy agreement
        agreement_bonus = min(0.20, (len(winning_signals) - 1) * 0.08)
        final_confidence = min(0.98, avg_confidence + agreement_bonus)

        if final_confidence < min_consensus_confidence:
            logger.debug(
                "Consensus confidence (%.2f) below minimum threshold (%.2f) for %s",
                final_confidence,
                min_consensus_confidence,
                symbol,
            )
            return None

        # Calculate weighted average entry price
        weighted_entry = sum(s.entry_price * s.confidence for s in winning_signals) / sum(
            s.confidence for s in winning_signals
        )

        # For Stop Loss: take conservative (safest) stop loss
        sl_list = [s.stop_loss for s in winning_signals if s.stop_loss is not None]
        if sl_list:
            final_sl = min(sl_list) if winning_side == SignalType.BUY else max(sl_list)
        else:
            final_sl = None

        # For Take Profit: average of TPs
        tp_list = [s.take_profit for s in winning_signals if s.take_profit is not None]
        final_tp = (sum(tp_list) / len(tp_list)) if tp_list else None

        # Aggregate reasoning
        reasons = [f"[{s.strategy_name} (conf={s.confidence:.2f})]: {s.reasoning}" for s in winning_signals]
        combined_reasoning = (
            f"Consensus {winning_side.value.upper()} signal for {symbol} supported by "
            f"{len(winning_signals)} strategies: " + " | ".join(reasons)
        )

        # Merge indicator snapshots
        merged_snapshot: Dict[str, Any] = {}
        for s in winning_signals:
            merged_snapshot[s.strategy_name] = s.indicators_snapshot

        now = datetime.now(timezone.utc)
        return Signal(
            symbol=symbol,
            signal_type=winning_side,
            strategy_name=f"Consensus({len(winning_signals)})",
            timeframe=winning_signals[0].timeframe,
            confidence=round(final_confidence, 2),
            entry_price=round(weighted_entry, 5),
            stop_loss=round(final_sl, 5) if final_sl is not None else None,
            take_profit=round(final_tp, 5) if final_tp is not None else None,
            reasoning=combined_reasoning,
            indicators_snapshot=merged_snapshot,
            timestamp=now,
            expired_at=now + timedelta(minutes=self.signal_validity_minutes),
        )

    def format_signal_reasoning(self, result: StrategyResult) -> str:
        """
        Creates a clear, human-readable justification of WHY the signal was fired.
        Never makes false claims of guaranteed profitability.
        """
        action = result.signal.value.upper()
        if not result.is_actionable:
            return f"[{result.strategy_name}] Neutral/Hold: {result.reasoning}"

        parts = [
            f"[{result.strategy_name}] {action} signal for {result.symbol} on {result.timeframe}.",
            f"Confidence: {result.confidence * 100:.1f}%.",
            f"Rationale: {result.reasoning}",
        ]
        if result.entry_price:
            parts.append(f"Entry: {result.entry_price:.5f}")
        if result.stop_loss:
            parts.append(f"SL: {result.stop_loss:.5f}")
        if result.take_profit:
            parts.append(f"TP: {result.take_profit:.5f}")

        return " ".join(parts)
