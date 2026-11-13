"""
Risk Manager module.
The core risk governance layer of the trading platform. Enforces margin requirements,
drawdown limits, daily loss boundaries, dynamic lot sizing, and emergency kill-switch.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.core.constants import OrderSide, SignalType
from app.core.logging_config import get_logger
from app.risk.position_sizer import PositionSizer
from app.risk.risk_metrics import RiskMetricsCalculator
from app.risk.stop_loss import StopLossCalculator

logger = get_logger("risk.manager")

# Safe settings getter fallback
def _get_default_risk_settings():
    try:
        from app.core.config import get_settings
        s = get_settings()
        return (
            getattr(s, "DEFAULT_RISK_PERCENT", 1.0),
            getattr(s, "MAX_DAILY_LOSS_PERCENT", 5.0),
            getattr(s, "MAX_OPEN_POSITIONS", 5),
            getattr(s, "MAX_DRAWDOWN_PERCENT", 10.0),
        )
    except Exception:
        return (1.0, 5.0, 5, 10.0)


@dataclass
class TradeValidationResult:
    """Trade validation result returned by RiskManager."""
    is_valid: bool
    reason: str
    rejection_code: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class RiskManager:
    """
    Central Risk Authority.
    Every trade executed in PAPER or LIVE mode must pass RiskManager validation.
    """

    def __init__(
        self,
        default_risk_percent: Optional[float] = None,
        max_daily_loss_percent: Optional[float] = None,
        max_open_positions: Optional[int] = None,
        max_drawdown_percent: Optional[float] = None,
        max_portfolio_heat_percent: float = 10.0,
        max_spread_pips: float = 4.0,
    ):
        def_risk, def_daily, def_pos, def_dd = _get_default_risk_settings()
        self.default_risk_percent = (
            default_risk_percent if default_risk_percent is not None else def_risk
        )
        self.max_daily_loss_percent = (
            max_daily_loss_percent if max_daily_loss_percent is not None else def_daily
        )
        self.max_open_positions = (
            max_open_positions if max_open_positions is not None else def_pos
        )
        self.max_drawdown_percent = (
            max_drawdown_percent if max_drawdown_percent is not None else def_dd
        )
        self.max_portfolio_heat_percent = max_portfolio_heat_percent
        self.max_spread_pips = max_spread_pips

        self.position_sizer = PositionSizer(default_risk_percent=self.default_risk_percent)
        self.stop_loss_calc = StopLossCalculator()
        self.metrics_calc = RiskMetricsCalculator()

        self._emergency_shutdown_active: bool = False
        self._peak_equity_tracker: Dict[str, float] = {}  # account_id -> peak_equity

    @property
    def is_shutdown(self) -> bool:
        """Returns True if the system is currently in emergency shutdown state."""
        return self._emergency_shutdown_active

    def trigger_emergency_shutdown(self, reason: str = "Manual emergency shutdown triggered") -> List[Dict[str, Any]]:
        """
        Activates emergency shutdown: halts all new order generation and returns
        instructions to immediately close all active positions.
        """
        self._emergency_shutdown_active = True
        logger.critical("EMERGENCY SHUTDOWN ACTIVATED: %s", reason)
        return [
            {
                "action": "CLOSE_ALL_POSITIONS",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "halt_trading": True,
            }
        ]

    def reset_emergency_shutdown(self) -> None:
        """Resets emergency shutdown flag after operator intervention."""
        self._emergency_shutdown_active = False
        logger.info("Emergency shutdown cleared by operator.")

    def calculate_position_size(
        self,
        symbol: str,
        account_balance: float,
        risk_percent: Optional[float],
        stop_loss_distance: float,
        symbol_info: Dict[str, Any],
        entry_price: Optional[float] = None,
    ) -> float:
        """
        Calculates broker-accurate lot size.
        NEVER assumes fixed pip value.
        """
        rp = risk_percent if risk_percent is not None else self.default_risk_percent
        return self.position_sizer.calculate_lot_size(
            account_balance=account_balance,
            risk_percent=rp,
            stop_loss_distance=stop_loss_distance,
            symbol_info=symbol_info,
            entry_price=entry_price,
        )

    def validate_trade(
        self,
        symbol: str,
        side: Union[OrderSide, SignalType, str],
        volume: float,
        entry_price: float,
        sl: Optional[float],
        tp: Optional[float],
        account_info: Dict[str, Any],
        symbol_info: Dict[str, Any],
        open_positions: Optional[List[Dict[str, Any]]] = None,
        daily_loss_amount: float = 0.0,
    ) -> TradeValidationResult:
        """
        Exhaustive trade pre-execution validation against all risk criteria.
        """
        # 1. Emergency shutdown check
        if self._emergency_shutdown_active:
            return TradeValidationResult(
                is_valid=False,
                reason="System is in EMERGENCY SHUTDOWN mode. All trading halted.",
                rejection_code="EMERGENCY_SHUTDOWN",
            )

        # 2. Volume sanity
        vol_min = float(symbol_info.get("volume_min", 0.01))
        vol_max = float(symbol_info.get("volume_max", 100.0))
        if volume < vol_min:
            return TradeValidationResult(
                is_valid=False,
                reason=f"Volume {volume} is below minimum allowed {vol_min}.",
                rejection_code="VOLUME_TOO_SMALL",
            )
        if volume > vol_max:
            return TradeValidationResult(
                is_valid=False,
                reason=f"Volume {volume} exceeds maximum allowed {vol_max}.",
                rejection_code="VOLUME_TOO_LARGE",
            )

        # 3. Stop loss requirement: A STOP LOSS IS MANDATORY FOR SAFETY
        if sl is None or sl <= 0:
            return TradeValidationResult(
                is_valid=False,
                reason="Stop loss is mandatory for all automated trades.",
                rejection_code="MISSING_STOP_LOSS",
            )

        # Standardize side
        side_str = side.value if isinstance(side, (OrderSide, SignalType)) else str(side).lower()
        if side_str == "buy" and sl >= entry_price:
            return TradeValidationResult(
                is_valid=False,
                reason=f"BUY SL ({sl}) must be lower than entry ({entry_price}).",
                rejection_code="INVALID_SL_BUY",
            )
        if side_str == "sell" and sl <= entry_price:
            return TradeValidationResult(
                is_valid=False,
                reason=f"SELL SL ({sl}) must be higher than entry ({entry_price}).",
                rejection_code="INVALID_SL_SELL",
            )

        # 4. Broker stop level distance validation
        is_stop_valid, min_allowed_sl = self.stop_loss_calc.validate_broker_stop_distance(
            entry_price, sl, symbol_info
        )
        if not is_stop_valid:
            return TradeValidationResult(
                is_valid=False,
                reason=(
                    f"Stop loss ({sl}) violates broker minimum stops_level distance. "
                    f"Minimum required SL is {min_allowed_sl}."
                ),
                rejection_code="BROKER_STOP_LEVEL_VIOLATION",
                details={"suggested_sl": min_allowed_sl},
            )

        # 5. Open positions count check
        open_positions = open_positions or []
        if not self.check_max_positions(len(open_positions), self.max_open_positions):
            return TradeValidationResult(
                is_valid=False,
                reason=f"Max open positions limit reached ({len(open_positions)} >= {self.max_open_positions}).",
                rejection_code="MAX_POSITIONS_REACHED",
                details={"open_positions": len(open_positions), "limit": self.max_open_positions},
            )

        # 6. Account Drawdown check
        balance = float(account_info.get("balance", 0.0))
        equity = float(account_info.get("equity", balance))
        account_id = str(account_info.get("login", account_info.get("id", "default")))
        peak = self._peak_equity_tracker.get(account_id, max(balance, equity))
        if equity > peak:
            peak = equity
            self._peak_equity_tracker[account_id] = peak

        if not self.check_max_drawdown(equity, peak, self.max_drawdown_percent):
            return TradeValidationResult(
                is_valid=False,
                reason=(
                    f"Account drawdown exceeded limit of {self.max_drawdown_percent}%. "
                    f"Current equity: {equity:.2f}, Peak equity: {peak:.2f}."
                ),
                rejection_code="MAX_DRAWDOWN_EXCEEDED",
                details={"equity": equity, "peak": peak, "limit_pct": self.max_drawdown_percent},
            )

        # 7. Daily loss limit check
        if not self.check_daily_loss(daily_loss_amount, self.max_daily_loss_percent, balance):
            return TradeValidationResult(
                is_valid=False,
                reason=(
                    f"Max daily loss reached: loss of ${daily_loss_amount:.2f} "
                    f"exceeds limit ({self.max_daily_loss_percent}% of balance ${balance:.2f})."
                ),
                rejection_code="DAILY_LOSS_LIMIT_REACHED",
                details={"daily_loss": daily_loss_amount, "limit_pct": self.max_daily_loss_percent},
            )

        # 8. Margin Requirement check
        free_margin = float(account_info.get("free_margin", account_info.get("margin_free", equity)))
        # Estimate required margin for this new position
        contract_size = float(symbol_info.get("trade_contract_size", 100000.0))
        leverage = float(account_info.get("leverage", 100.0))
        if leverage <= 0:
            leverage = 100.0
        required_margin = (volume * contract_size * entry_price) / leverage
        # Account currency conversion factor if needed; for base USD accounts approx.
        if not self.check_margin_requirement(required_margin, free_margin):
            return TradeValidationResult(
                is_valid=False,
                reason=(
                    f"Insufficient free margin for order. "
                    f"Required: ${required_margin:.2f}, Free: ${free_margin:.2f}."
                ),
                rejection_code="INSUFFICIENT_MARGIN",
                details={"required_margin": required_margin, "free_margin": free_margin},
            )

        # 9. Portfolio heat check
        heat_pct = self.metrics_calc.calculate_portfolio_heat(open_positions, equity)
        sl_dist = abs(entry_price - sl)
        new_trade_risk_pct = self.metrics_calc.calculate_position_risk_percent(
            volume, sl_dist, balance, symbol_info
        )
        if heat_pct + new_trade_risk_pct > self.max_portfolio_heat_percent:
            return TradeValidationResult(
                is_valid=False,
                reason=(
                    f"Trade would push portfolio heat to {heat_pct + new_trade_risk_pct:.1f}%, "
                    f"exceeding max limit of {self.max_portfolio_heat_percent:.1f}%."
                ),
                rejection_code="PORTFOLIO_HEAT_LIMIT",
                details={"current_heat": heat_pct, "trade_risk": new_trade_risk_pct},
            )

        return TradeValidationResult(
            is_valid=True,
            reason="Trade approved by RiskManager.",
            details={
                "volume": volume,
                "sl": sl,
                "tp": tp,
                "estimated_risk_pct": new_trade_risk_pct,
                "portfolio_heat_after": heat_pct + new_trade_risk_pct,
            },
        )

    def check_daily_loss(
        self, daily_loss_amount: float, max_daily_loss_percent: float, starting_balance: float
    ) -> bool:
        """
        Checks if accumulated daily loss exceeds maximum daily loss percentage.
        Returns True if within acceptable limits, False if limit exceeded.
        """
        if starting_balance <= 0:
            return False
        max_allowed_loss_dollars = starting_balance * (max_daily_loss_percent / 100.0)
        return abs(daily_loss_amount) < max_allowed_loss_dollars

    def check_max_drawdown(
        self, equity: float, peak_equity: float, max_drawdown_percent: float
    ) -> bool:
        """
        Checks if current account drawdown is within maximum threshold.
        """
        if peak_equity <= 0:
            return True
        drawdown_dollars = peak_equity - equity
        if drawdown_dollars <= 0:
            return True
        drawdown_pct = (drawdown_dollars / peak_equity) * 100.0
        return drawdown_pct < max_drawdown_percent

    def check_max_positions(self, open_positions_count: int, max_positions: int) -> bool:
        """
        Checks whether open position count is under maximum limit.
        """
        return open_positions_count < max_positions

    def check_margin_requirement(self, required_margin: float, free_margin: float) -> bool:
        """
        Ensures sufficient free margin remains, keeping a 10% safety cushion.
        """
        safety_cushion = required_margin * 1.10
        return free_margin >= safety_cushion

    def check_spread(
        self, current_spread_points_or_pips: float, max_spread_pips: Optional[float] = None
    ) -> bool:
        """
        Checks if current spread is acceptable.
        """
        max_spread = max_spread_pips if max_spread_pips is not None else self.max_spread_pips
        return current_spread_points_or_pips <= max_spread
