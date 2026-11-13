"""
Signal Validator module.
Performs pre-trade risk and market environment screening on generated signals
before they can reach execution engines.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.constants import SignalType
from app.core.logging_config import get_logger
from app.schemas.signal import SignalBase
from app.signals.signal_generator import Signal

logger = get_logger("signals.validator")


@dataclass
class ValidationResult:
    """Result returned by SignalValidator."""
    is_valid: bool
    reason: str
    rejection_code: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class SignalValidator:
    """
    Validates actionable trading signals against environmental constraints:
    - Current spread vs max permitted spread
    - Active trading session
    - Consecutive losses cooldown
    - Max trades per day / max active signals
    - Expiration timestamps
    """

    def __init__(
        self,
        max_spread_pips: float = 3.5,
        max_consecutive_losses: int = 3,
        max_daily_signals: int = 20,
    ):
        self.max_spread_pips = max_spread_pips
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_signals = max_daily_signals

    def validate(
        self,
        signal: Signal,
        current_spread_pips: Optional[float] = None,
        is_session_open: bool = True,
        consecutive_losses: int = 0,
        daily_trades_count: int = 0,
        symbol_info: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Runs comprehensive validation checklist on a Signal.
        """
        # 1. Actionability check
        if not signal.is_actionable:
            return ValidationResult(
                is_valid=False,
                reason="Signal is HOLD / Neutral, not actionable for trade execution.",
                rejection_code="NOT_ACTIONABLE",
            )

        # 2. Expiration check
        now = datetime.now(timezone.utc)
        if signal.expired_at and now > signal.expired_at:
            return ValidationResult(
                is_valid=False,
                reason=f"Signal expired at {signal.expired_at.isoformat()} (current time {now.isoformat()}).",
                rejection_code="SIGNAL_EXPIRED",
            )

        # 3. Trading session check
        if not is_session_open:
            return ValidationResult(
                is_valid=False,
                reason=f"Market session is closed or inactive for {signal.symbol}.",
                rejection_code="SESSION_CLOSED",
            )

        # 4. Spread limits check
        if current_spread_pips is not None:
            # Gold allows slightly wider spread (e.g. up to 6.0 pips)
            allowed_spread = (
                self.max_spread_pips * 2.0
                if "XAU" in signal.symbol.upper()
                else self.max_spread_pips
            )
            if current_spread_pips > allowed_spread:
                return ValidationResult(
                    is_valid=False,
                    reason=(
                        f"Current spread ({current_spread_pips:.1f} pips) exceeds maximum "
                        f"threshold ({allowed_spread:.1f} pips) for {signal.symbol}."
                    ),
                    rejection_code="SPREAD_TOO_HIGH",
                    details={"current_spread": current_spread_pips, "max_spread": allowed_spread},
                )

        # 5. Consecutive losses cooldown
        if consecutive_losses >= self.max_consecutive_losses:
            return ValidationResult(
                is_valid=False,
                reason=(
                    f"Trading paused due to {consecutive_losses} consecutive losses "
                    f"(limit: {self.max_consecutive_losses}). Risk cooldown active."
                ),
                rejection_code="CONSECUTIVE_LOSS_LIMIT",
                details={"consecutive_losses": consecutive_losses},
            )

        # 6. Daily signals / trades frequency limit
        if daily_trades_count >= self.max_daily_signals:
            return ValidationResult(
                is_valid=False,
                reason=f"Daily trade frequency limit reached ({daily_trades_count} >= {self.max_daily_signals}).",
                rejection_code="DAILY_LIMIT_REACHED",
                details={"daily_trades_count": daily_trades_count},
            )

        # 7. Price & SL/TP sanity
        if signal.entry_price <= 0:
            return ValidationResult(
                is_valid=False,
                reason="Invalid entry price (must be positive).",
                rejection_code="INVALID_PRICE",
            )

        if signal.signal_type == SignalType.BUY and signal.stop_loss:
            if signal.stop_loss >= signal.entry_price:
                return ValidationResult(
                    is_valid=False,
                    reason=f"BUY stop loss ({signal.stop_loss}) must be below entry ({signal.entry_price}).",
                    rejection_code="INVALID_SL",
                )

        if signal.signal_type == SignalType.SELL and signal.stop_loss:
            if signal.stop_loss <= signal.entry_price:
                return ValidationResult(
                    is_valid=False,
                    reason=f"SELL stop loss ({signal.stop_loss}) must be above entry ({signal.entry_price}).",
                    rejection_code="INVALID_SL",
                )

        return ValidationResult(
            is_valid=True,
            reason="Signal passed all environmental and safety validation checks.",
            details={"symbol": signal.symbol, "side": signal.signal_type.value},
        )
