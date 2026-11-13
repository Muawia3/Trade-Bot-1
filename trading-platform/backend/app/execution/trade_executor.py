"""
Trade Execution Engine.

Responsible for pre-trade safety verification, dynamic position sizing,
risk parameter compliance, and order routing between the Paper Trading Engine
and live MT5 bridge.

CRITICAL SAFETY DIRECTIVE:
Live trades are NEVER sent to the MT5 bridge unless TRADING_MODE is LIVE
AND LIVE_TRADING_ENABLED is explicitly True in configuration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.core.config import TradingMode, get_settings
from app.core.constants import (
    MAX_LOT_SIZE,
    MIN_LOT_SIZE,
    OrderSide,
    SignalType,
)
from app.core.logging_config import get_logger
from app.paper_trading.paper_engine import (
    PaperTradingEngine,
    PaperTradeResult,
)

logger = get_logger("execution.trade_executor")


@dataclass
class TradeResult:
    """Standardized result returned from trade execution."""

    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    volume: float = 0.0
    price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    trading_mode: str = "PAPER"
    message: str = ""
    execution_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert trade result to dictionary format."""
        return {
            "success": self.success,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "price": round(self.price, 5),
            "sl": round(self.sl, 5) if self.sl is not None else None,
            "tp": round(self.tp, 5) if self.tp is not None else None,
            "trading_mode": self.trading_mode,
            "message": self.message,
            "execution_time": self.execution_time.isoformat(),
            "details": self.details,
        }


class TradeExecutor:
    """
    Executes trading signals safely across Paper and Live environments.

    Coordinates:
    - Pre-trade checklist checks (spread, market open, margin, risk limits)
    - Position sizing calculation based on account equity and stop loss distance
    - Execution routing to PaperTradingEngine or MT5 Bridge
    - Safety isolation and audit logging
    """

    def __init__(
        self,
        paper_engine: Optional[PaperTradingEngine] = None,
        risk_manager: Optional[Any] = None,
        mt5_order_service: Optional[Any] = None,
    ) -> None:
        self.settings = get_settings()
        self.paper_engine = paper_engine or PaperTradingEngine()
        self.risk_manager = risk_manager
        self.mt5_order_service = mt5_order_service

        logger.info(
            "TradeExecutor initialized. Mode: %s (Live Enabled: %s)",
            self.settings.TRADING_MODE.value,
            self.settings.LIVE_TRADING_ENABLED,
        )

    # -------------------------------------------------------------------------
    # Pre-trade Checklist
    # -------------------------------------------------------------------------
    def pre_trade_checklist(
        self,
        symbol: str,
        side: OrderSide,
        entry_price: float,
        sl: Optional[float],
        tp: Optional[float],
        volume: float,
        account_info: Dict[str, Any],
        symbol_info: Dict[str, Any],
        risk_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Comprehensive pre-trade verification checklist.

        Checks:
        1. Market Open: Verify day of week and session availability.
        2. Valid Spread: Current spread must not exceed maximum tolerance.
        3. Risk Limits: Open positions, daily drawdown, account drawdown within limits.
        4. Margin Sufficient: Account must have enough free margin.
        5. Stop Loss Set: Every single trade MUST have a valid stop loss.
        6. Position Size Valid: Volume within broker min/max bounds and valid lot step.
        """
        checklist_details: Dict[str, Any] = {}
        risk_params = risk_params or {}

        # 1. Market Open Check
        now_utc = datetime.now(timezone.utc)
        # Saturday is day 5, Sunday is day 6
        if now_utc.weekday() == 5:  # Saturday
            return False, "Market is closed on Saturdays.", checklist_details
        if now_utc.weekday() == 6 and now_utc.hour < 21:  # Sunday before 21:00 UTC
            return False, "Market is closed on Sundays prior to 21:00 UTC.", checklist_details

        is_market_open = symbol_info.get("trade_mode_open", True)
        if not is_market_open:
            return False, f"Trading is halted or market closed for {symbol}.", checklist_details
        checklist_details["market_open"] = True

        # 2. Valid Spread Check
        spread_pips = symbol_info.get("spread_pips")
        if spread_pips is None:
            # Calculate from ask - bid if provided
            ask = symbol_info.get("ask", entry_price)
            bid = symbol_info.get("bid", entry_price)
            pip_size = symbol_info.get("pip_size", 0.0001 if "JPY" not in symbol and "XAU" not in symbol else 0.01)
            spread_pips = abs(ask - bid) / pip_size if pip_size > 0 else 1.0

        max_spread = risk_params.get("max_spread_pips", 5.0 if "XAU" in symbol else 3.0)
        checklist_details["spread_pips"] = round(spread_pips, 2)
        checklist_details["max_allowed_spread"] = max_spread

        if spread_pips > max_spread:
            return (
                False,
                f"Spread too wide ({spread_pips:.1f} pips > max {max_spread:.1f} pips). Trade rejected.",
                checklist_details,
            )

        # 3. Stop Loss Set Check (CRITICAL RISK RULE)
        if sl is None or sl <= 0:
            return False, "Mandatory safety rule violated: Stop Loss is not set or non-positive.", checklist_details

        if side == OrderSide.BUY and sl >= entry_price:
            return (
                False,
                f"Invalid Buy SL ({sl:.5f} >= Entry {entry_price:.5f}). SL must be below entry.",
                checklist_details,
            )
        if side == OrderSide.SELL and sl <= entry_price:
            return (
                False,
                f"Invalid Sell SL ({sl:.5f} <= Entry {entry_price:.5f}). SL must be above entry.",
                checklist_details,
            )
        checklist_details["stop_loss_valid"] = True

        # 4. Position Size Valid
        min_lot = symbol_info.get("volume_min", MIN_LOT_SIZE)
        max_lot = symbol_info.get("volume_max", MAX_LOT_SIZE)
        lot_step = symbol_info.get("volume_step", 0.01)

        if volume < min_lot:
            return (
                False,
                f"Calculated volume ({volume:.2f}) is below minimum allowed lot ({min_lot}).",
                checklist_details,
            )
        if volume > max_lot:
            return (
                False,
                f"Calculated volume ({volume:.2f}) exceeds maximum allowed lot ({max_lot}).",
                checklist_details,
            )
        checklist_details["volume_valid"] = True

        # 5. Risk Limits (Open positions & daily drawdown)
        open_positions = account_info.get("open_positions_count", 0)
        max_open = risk_params.get("max_open_positions", self.settings.MAX_OPEN_POSITIONS)
        if open_positions >= max_open:
            return (
                False,
                f"Max open positions reached ({open_positions}/{max_open}).",
                checklist_details,
            )

        daily_loss_pct = account_info.get("daily_loss_percent", 0.0)
        max_daily_loss = risk_params.get(
            "max_daily_loss_percent", self.settings.MAX_DAILY_LOSS_PERCENT
        )
        if daily_loss_pct >= max_daily_loss:
            return (
                False,
                f"Daily loss limit reached ({daily_loss_pct:.2f}% >= {max_daily_loss:.2f}%). Trading halted.",
                checklist_details,
            )

        # 6. Margin Sufficient Check
        free_margin = account_info.get("free_margin", account_info.get("balance", 10000.0))
        leverage = account_info.get("leverage", 100.0)
        contract_size = symbol_info.get("contract_size", 100000.0 if "XAU" not in symbol else 100.0)
        notional = volume * contract_size * entry_price
        required_margin = notional / leverage if leverage > 0 else notional

        checklist_details["required_margin"] = round(required_margin, 2)
        checklist_details["free_margin"] = round(free_margin, 2)

        if required_margin > (free_margin * 0.95):  # 5% safety buffer
            return (
                False,
                f"Insufficient margin. Required: ${required_margin:.2f}, Available Free Margin: ${free_margin:.2f}",
                checklist_details,
            )

        return True, "Pre-trade checklist PASSED.", checklist_details

    # -------------------------------------------------------------------------
    # Position Sizing
    # -------------------------------------------------------------------------
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        risk_percent: Optional[float] = None,
        symbol_info: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate safe position size based on equity percentage risk and stop loss distance.

        Formula:
          Risk Amount = Equity * (Risk % / 100)
          SL Distance (pips) = |Entry - SL| / Pip Size
          Lot Size = Risk Amount / (SL Distance * Pip Value per lot)
        """
        # If external RiskManager attached, delegate to it
        if self.risk_manager and hasattr(self.risk_manager, "calculate_position_size"):
            try:
                calculated = self.risk_manager.calculate_position_size(
                    symbol=symbol,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    equity=account_equity,
                    risk_percent=risk_percent,
                    symbol_info=symbol_info,
                )
                if calculated and calculated > 0:
                    return round(calculated, 2)
            except Exception as e:
                logger.warning("RiskManager position size calculation failed: %s. Using internal sizing.", e)

        info = symbol_info or {}
        risk_pct = risk_percent if risk_percent is not None else self.settings.DEFAULT_RISK_PERCENT
        risk_amount = account_equity * (risk_pct / 100.0)

        # Determine pip size and contract size
        sym = symbol.upper()
        if "XAU" in sym:
            pip_size = info.get("pip_size", 0.01)
            contract_size = info.get("contract_size", 100.0)
        elif "JPY" in sym:
            pip_size = info.get("pip_size", 0.01)
            contract_size = info.get("contract_size", 100000.0)
        else:
            pip_size = info.get("pip_size", 0.0001)
            contract_size = info.get("contract_size", 100000.0)

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return MIN_LOT_SIZE

        sl_pips = sl_distance / pip_size

        # Pip value per standard 1.0 lot
        if sym.endswith("USD"):
            pip_val_per_lot = contract_size * pip_size
        elif sym.startswith("USD"):
            pip_val_per_lot = (contract_size * pip_size / entry_price) if entry_price > 0 else 10.0
        else:
            pip_val_per_lot = 10.0

        if sl_pips * pip_val_per_lot <= 0:
            return MIN_LOT_SIZE

        raw_lot = risk_amount / (sl_pips * pip_val_per_lot)

        # Quantize to lot step
        lot_step = info.get("volume_step", 0.01)
        min_lot = info.get("volume_min", MIN_LOT_SIZE)
        max_lot = info.get("volume_max", MAX_LOT_SIZE)

        steps = math.floor(round(raw_lot / lot_step, 6))
        final_lot = steps * lot_step

        final_lot = max(min_lot, min(final_lot, max_lot))
        return round(final_lot, 2)

    # -------------------------------------------------------------------------
    # Execute Signal
    # -------------------------------------------------------------------------
    def execute_signal(
        self,
        signal: Any,
        account_info: Dict[str, Any],
        symbol_info: Dict[str, Any],
        risk_params: Optional[Dict[str, Any]] = None,
    ) -> TradeResult:
        """
        Execute an incoming trading signal with strict risk validation and mode routing.

        Signal can be an instance of SignalBase / SignalCreate / dict.
        """
        # Extract signal fields
        if hasattr(signal, "symbol"):
            sym = signal.symbol
            raw_sig = getattr(signal, "signal_type", None)
            if raw_sig is None:
                raw_sig = getattr(signal, "signal", "")
            sig_type = raw_sig.value if hasattr(raw_sig, "value") else str(raw_sig)
            entry_price = float(signal.entry_price) if getattr(signal, "entry_price", None) is not None else 0.0
            sl = float(signal.stop_loss) if getattr(signal, "stop_loss", None) is not None else None
            tp = float(signal.take_profit) if getattr(signal, "take_profit", None) is not None else None
            strategy_name = getattr(signal, "strategy_name", "unknown")
            confidence = getattr(signal, "confidence", 1.0)
        elif isinstance(signal, dict):
            sym = signal.get("symbol", "")
            raw_sig = signal.get("signal_type", signal.get("signal", ""))
            sig_type = raw_sig.value if hasattr(raw_sig, "value") else str(raw_sig)
            entry_price = float(signal.get("entry_price", 0.0))
            sl = float(signal["stop_loss"]) if signal.get("stop_loss") is not None else None
            tp = float(signal["take_profit"]) if signal.get("take_profit") is not None else None
            strategy_name = signal.get("strategy_name", "unknown")
            confidence = float(signal.get("confidence", 1.0))
        else:
            return TradeResult(
                success=False,
                message=f"Unsupported signal type: {type(signal).__name__}",
            )

        # Ignore HOLD signals
        side_str = sig_type.upper()
        if side_str in ("HOLD", "FLAT", "NEUTRAL"):
            return TradeResult(
                success=True,
                symbol=sym,
                side="HOLD",
                message="Signal is HOLD. No order executed.",
            )

        if side_str not in ("BUY", "SELL"):
            return TradeResult(
                success=False,
                symbol=sym,
                message=f"Invalid signal type: {sig_type}. Expected BUY or SELL.",
            )

        order_side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL

        # Determine account equity
        equity = float(account_info.get("equity", account_info.get("balance", 10000.0)))

        # Sizing
        volume = self.calculate_position_size(
            symbol=sym,
            entry_price=entry_price,
            stop_loss=sl if sl is not None else (entry_price * 0.99 if order_side == OrderSide.BUY else entry_price * 1.01),
            account_equity=equity,
            risk_percent=risk_params.get("risk_percent") if risk_params else None,
            symbol_info=symbol_info,
        )

        # Run Pre-Trade Checklist
        passed, reason, checklist_meta = self.pre_trade_checklist(
            symbol=sym,
            side=order_side,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            volume=volume,
            account_info=account_info,
            symbol_info=symbol_info,
            risk_params=risk_params,
        )

        if not passed:
            logger.warning(
                "Pre-trade checklist rejected signal for %s [%s]: %s",
                sym,
                side_str,
                reason,
            )
            return TradeResult(
                success=False,
                symbol=sym,
                side=side_str,
                volume=volume,
                price=entry_price,
                sl=sl,
                tp=tp,
                message=f"Pre-trade checklist failed: {reason}",
                details={"checklist": checklist_meta},
            )

        # Routing Decision
        is_live = self.settings.is_live_trading

        # Mode Safety Enforcer: Never allow live trading without explicit double-enablement
        if is_live:
            if not self.settings.LIVE_TRADING_ENABLED or self.settings.TRADING_MODE != TradingMode.LIVE:
                logger.critical(
                    "SECURITY ALERT: Inconsistent live configuration detected! Falling back to PAPER."
                )
                is_live = False

        if is_live:
            # Execute LIVE trade via MT5 Order Service
            logger.warning(
                "🚨 EXECUTING LIVE TRADE on MT5: %s %s %.2f lots @ %.5f | SL: %s, TP: %s 🚨",
                sym,
                side_str,
                volume,
                entry_price,
                sl,
                tp,
            )
            return self._execute_live(
                symbol=sym,
                side=order_side,
                volume=volume,
                price=entry_price,
                sl=sl,
                tp=tp,
                strategy_name=strategy_name,
                confidence=confidence,
                details=checklist_meta,
            )
        else:
            # Execute PAPER trade
            logger.info(
                "Executing PAPER trade: %s %s %.2f lots @ %.5f | Strategy: %s",
                sym,
                side_str,
                volume,
                entry_price,
                strategy_name,
            )
            return self._execute_paper(
                symbol=sym,
                side=order_side,
                volume=volume,
                price=entry_price,
                sl=sl,
                tp=tp,
                strategy_name=strategy_name,
                confidence=confidence,
                details=checklist_meta,
            )

    # -------------------------------------------------------------------------
    # Route Implementations
    # -------------------------------------------------------------------------
    def _execute_paper(
        self,
        symbol: str,
        side: OrderSide,
        volume: float,
        price: float,
        sl: Optional[float],
        tp: Optional[float],
        strategy_name: str,
        confidence: float,
        details: Dict[str, Any],
    ) -> TradeResult:
        """Execute trade on Paper Trading Engine."""
        comment = f"{strategy_name} (conf:{confidence:.2f})"
        res = self.paper_engine.open_position(
            symbol=symbol,
            side=side,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            comment=comment,
        )

        details.update(res.details)
        return TradeResult(
            success=res.success,
            order_id=res.position_id,
            symbol=symbol,
            side=side.value,
            volume=volume,
            price=res.price if res.price > 0 else price,
            sl=sl,
            tp=tp,
            trading_mode="PAPER",
            message=res.message,
            details=details,
        )

    def _execute_live(
        self,
        symbol: str,
        side: OrderSide,
        volume: float,
        price: float,
        sl: Optional[float],
        tp: Optional[float],
        strategy_name: str,
        confidence: float,
        details: Dict[str, Any],
    ) -> TradeResult:
        """Route order to MT5 Bridge Service for live market execution."""
        if self.mt5_order_service is None:
            # Fallback import of order_service if available
            try:
                from mt5_bridge.services.order_service import order_service
                self.mt5_order_service = order_service
            except Exception as e:
                logger.error("Failed to load MT5 order service: %s", e)
                return TradeResult(
                    success=False,
                    symbol=symbol,
                    trading_mode="LIVE",
                    message=f"MT5 order service not available: {e}",
                    details=details,
                )

        try:
            comment = f"{strategy_name[:15]}_{confidence:.2f}"
            order_res = self.mt5_order_service.open_market_order(
                symbol=symbol,
                side=side.value.lower(),
                volume=volume,
                stop_loss=sl,
                take_profit=tp,
                comment=comment,
            )

            if order_res.success:
                logger.info(
                    "Live MT5 order succeeded. Ticket: %s, Deal: %s",
                    order_res.ticket,
                    order_res.deal_id,
                )
                return TradeResult(
                    success=True,
                    order_id=str(order_res.ticket),
                    symbol=symbol,
                    side=side.value,
                    volume=volume,
                    price=order_res.fill_price or price,
                    sl=sl,
                    tp=tp,
                    trading_mode="LIVE",
                    message="Live MT5 order filled successfully.",
                    details={"ticket": order_res.ticket, "deal_id": order_res.deal_id},
                )
            else:
                logger.error("Live MT5 order failed: %s", order_res.error_message)
                return TradeResult(
                    success=False,
                    symbol=symbol,
                    side=side.value,
                    volume=volume,
                    price=price,
                    trading_mode="LIVE",
                    message=f"MT5 execution error: {order_res.error_message}",
                    details={"error_code": order_res.retcode},
                )
        except Exception as ex:
            logger.exception("Exception during live order execution: %s", ex)
            return TradeResult(
                success=False,
                symbol=symbol,
                side=side.value,
                trading_mode="LIVE",
                message=f"Live execution exception: {str(ex)}",
            )
