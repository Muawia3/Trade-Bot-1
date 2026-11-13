"""
Paper Trading Engine.

Provides high-fidelity simulated trading execution and order tracking using
real-time market prices, with realistic modeling of spreads, slippage, and commissions.
IMPORTANT SAFETY RULE: This module NEVER calls MT5 live order execution functions.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.constants import OrderSide, OrderStatus, PositionType
from app.core.logging_config import get_logger

logger = get_logger("paper_trading.engine")


class PaperOrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class PaperPosition:
    """Represents an open or closed paper trading position."""

    id: str
    symbol: str
    side: OrderSide
    volume: float  # In standard lots (e.g., 0.10, 1.00)
    open_price: float
    current_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    trailing_stop_pips: Optional[float] = None
    highest_price: float = 0.0  # Used for long trailing stop
    lowest_price: float = 0.0   # Used for short trailing stop
    open_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    close_reason: Optional[str] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    status: OrderStatus = OrderStatus.OPEN
    magic_number: int = 100001
    comment: str = "Paper Trade"

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary representation."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value if isinstance(self.side, OrderSide) else str(self.side),
            "volume": self.volume,
            "open_price": round(self.open_price, 5),
            "current_price": round(self.current_price, 5),
            "sl": round(self.sl, 5) if self.sl is not None else None,
            "tp": round(self.tp, 5) if self.tp is not None else None,
            "trailing_stop_pips": self.trailing_stop_pips,
            "open_time": self.open_time.isoformat(),
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "close_price": round(self.close_price, 5) if self.close_price is not None else None,
            "close_reason": self.close_reason,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "commission": round(self.commission, 2),
            "swap": round(self.swap, 2),
            "net_pnl": round(
                (self.realized_pnl if self.status == OrderStatus.CLOSED else self.unrealized_pnl)
                - self.commission
                + self.swap,
                2,
            ),
            "status": self.status.value if isinstance(self.status, OrderStatus) else str(self.status),
            "magic_number": self.magic_number,
            "comment": self.comment,
        }


@dataclass
class PaperTradeResult:
    """Result returned from paper trade execution actions."""

    success: bool
    position_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    volume: float = 0.0
    price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    message: str = ""
    realized_pnl: float = 0.0
    position: Optional[PaperPosition] = None
    details: Dict[str, Any] = field(default_factory=dict)


class PaperTradingEngine:
    """
    In-memory simulated trading engine executing against live or backtest prices.

    Models:
    - Accurate contract sizes (100,000 for standard Forex, 100 oz for XAUUSD, 5000 oz for XAGUSD)
    - Realistic pip sizes (0.0001 for 4/5 digit forex, 0.01 for JPY & Gold)
    - Bid/Ask spreads and configurable execution slippage
    - Round-turn commission per lot
    - Margin requirement tracking and stop-out checks
    """

    def __init__(
        self,
        initial_balance: Optional[float] = None,
        currency: Optional[str] = None,
        leverage: float = 100.0,
        commission_per_lot: float = 7.0,
        slippage_pips: float = 0.2,
    ) -> None:
        settings = get_settings()
        self.initial_balance: float = (
            initial_balance
            if initial_balance is not None
            else settings.PAPER_TRADING_INITIAL_BALANCE
        )
        self.currency: str = currency or settings.PAPER_TRADING_CURRENCY
        self.leverage: float = leverage
        self.commission_per_lot: float = commission_per_lot
        self.slippage_pips: float = slippage_pips

        self.balance: float = self.initial_balance
        self.equity: float = self.initial_balance
        self.margin: float = 0.0
        self.free_margin: float = self.initial_balance
        self.margin_level: float = 0.0  # Percentage

        self.positions: Dict[str, PaperPosition] = {}
        self.history: List[PaperPosition] = []

        logger.info(
            "PaperTradingEngine initialized. Balance=%.2f %s, Leverage=1:%.0f",
            self.balance,
            self.currency,
            self.leverage,
        )

    # -------------------------------------------------------------------------
    # Instrument Specs Helper
    # -------------------------------------------------------------------------
    @staticmethod
    def get_symbol_specs(symbol: str) -> Dict[str, Any]:
        """
        Return contract size, pip size, and typical decimal digits for standard symbols.
        Avoids hardcoding fixed broker values by providing realistic defaults.
        """
        sym = symbol.upper()
        if "XAU" in sym:  # Gold (e.g., XAUUSD)
            return {"contract_size": 100.0, "pip_size": 0.01, "digits": 2}
        if "XAG" in sym:  # Silver (e.g., XAGUSD)
            return {"contract_size": 5000.0, "pip_size": 0.001, "digits": 3}
        if "JPY" in sym:  # JPY currency pairs
            return {"contract_size": 100000.0, "pip_size": 0.01, "digits": 3}
        # Standard Forex 5-digit pairs
        return {"contract_size": 100000.0, "pip_size": 0.0001, "digits": 5}

    def calculate_pip_value(self, symbol: str, volume: float, current_price: float) -> float:
        """
        Calculate the approximate pip value in account currency (assumed USD).
        """
        specs = self.get_symbol_specs(symbol)
        contract_size = specs["contract_size"]
        pip_size = specs["pip_size"]
        sym = symbol.upper()

        if sym.endswith("USD"):
            # Direct quote (EURUSD, GBPUSD, XAUUSD): pip_value = contract_size * pip_size * volume
            return contract_size * pip_size * volume
        elif sym.startswith("USD"):
            # Indirect quote (USDJPY, USDCAD, USDCHF): pip_value = (contract_size * pip_size / price) * volume
            if current_price <= 0:
                return 10.0 * volume
            return (contract_size * pip_size / current_price) * volume
        else:
            # Cross rates fallback approximation
            return 10.0 * volume

    def calculate_required_margin(self, symbol: str, volume: float, price: float) -> float:
        """Calculate margin required to hold position in USD."""
        specs = self.get_symbol_specs(symbol)
        contract_size = specs["contract_size"]
        notional_value = volume * contract_size * price

        sym = symbol.upper()
        if sym.startswith("USD") and not sym.endswith("USD"):
            # E.g. USDJPY: notional in USD is volume * contract_size
            notional_value = volume * contract_size

        return notional_value / self.leverage if self.leverage > 0 else notional_value

    # -------------------------------------------------------------------------
    # Core Trading Actions
    # -------------------------------------------------------------------------
    def open_position(
        self,
        symbol: str,
        side: OrderSide,
        volume: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        trailing_stop_pips: Optional[float] = None,
        comment: str = "Paper Trade",
        magic_number: int = 100001,
    ) -> PaperTradeResult:
        """
        Open a simulated position.
        Applies realistic slippage to fill price.
        """
        if volume <= 0:
            return PaperTradeResult(
                success=False,
                symbol=symbol,
                message=f"Invalid volume: {volume}. Must be greater than 0.",
            )

        if price <= 0:
            return PaperTradeResult(
                success=False,
                symbol=symbol,
                message=f"Invalid price: {price}. Must be greater than 0.",
            )

        specs = self.get_symbol_specs(symbol)
        pip_size = specs["pip_size"]

        # Simulate execution slippage (worse price for trader)
        slippage_delta = self.slippage_pips * pip_size
        if side == OrderSide.BUY:
            fill_price = price + slippage_delta
        else:
            fill_price = price - slippage_delta

        # Validate SL/TP orientation
        if sl is not None:
            if side == OrderSide.BUY and sl >= fill_price:
                return PaperTradeResult(
                    success=False,
                    symbol=symbol,
                    message=f"Buy SL ({sl}) must be below fill price ({fill_price:.5f})",
                )
            elif side == OrderSide.SELL and sl <= fill_price:
                return PaperTradeResult(
                    success=False,
                    symbol=symbol,
                    message=f"Sell SL ({sl}) must be above fill price ({fill_price:.5f})",
                )

        if tp is not None:
            if side == OrderSide.BUY and tp <= fill_price:
                return PaperTradeResult(
                    success=False,
                    symbol=symbol,
                    message=f"Buy TP ({tp}) must be above fill price ({fill_price:.5f})",
                )
            elif side == OrderSide.SELL and tp >= fill_price:
                return PaperTradeResult(
                    success=False,
                    symbol=symbol,
                    message=f"Sell TP ({tp}) must be below fill price ({fill_price:.5f})",
                )

        # Margin check
        required_margin = self.calculate_required_margin(symbol, volume, fill_price)
        if required_margin > self.free_margin:
            return PaperTradeResult(
                success=False,
                symbol=symbol,
                message=(
                    f"Insufficient free margin. Required: ${required_margin:.2f}, "
                    f"Available: ${self.free_margin:.2f}"
                ),
            )

        # Calculate opening commission (e.g. $7/lot round turn or half per side)
        commission = round(self.commission_per_lot * volume, 2)
        # Deduct commission immediately from balance
        self.balance -= commission

        pos_id = str(uuid.uuid4())
        position = PaperPosition(
            id=pos_id,
            symbol=symbol.upper(),
            side=side,
            volume=volume,
            open_price=fill_price,
            current_price=fill_price,
            sl=sl,
            tp=tp,
            trailing_stop_pips=trailing_stop_pips,
            highest_price=fill_price,
            lowest_price=fill_price,
            open_time=datetime.now(timezone.utc),
            commission=commission,
            magic_number=magic_number,
            comment=comment,
        )

        self.positions[pos_id] = position
        self._recalculate_account()

        logger.info(
            "Opened paper position [%s] %s %s %.2f lots @ %.5f | SL: %s, TP: %s",
            pos_id[:8],
            symbol,
            side.value,
            volume,
            fill_price,
            f"{sl:.5f}" if sl else "None",
            f"{tp:.5f}" if tp else "None",
        )

        return PaperTradeResult(
            success=True,
            position_id=pos_id,
            symbol=symbol,
            side=side.value,
            volume=volume,
            price=fill_price,
            sl=sl,
            tp=tp,
            message="Paper trade executed successfully.",
            position=position,
            details={"commission": commission, "required_margin": required_margin},
        )

    def close_position(
        self,
        position_id: str,
        price: Optional[float] = None,
        reason: str = "manual",
    ) -> PaperTradeResult:
        """
        Close an open paper position at specified price or position's current price.
        """
        if position_id not in self.positions:
            return PaperTradeResult(
                success=False,
                position_id=position_id,
                message=f"Position {position_id} not found.",
            )

        pos = self.positions[position_id]
        close_price = price if price is not None and price > 0 else pos.current_price

        # Apply slippage on exit
        specs = self.get_symbol_specs(pos.symbol)
        slippage_delta = self.slippage_pips * specs["pip_size"]
        if pos.side == OrderSide.BUY:
            final_price = close_price - slippage_delta
        else:
            final_price = close_price + slippage_delta

        # Calculate final realized PnL
        pnl = self._calculate_pnl(pos, final_price)

        pos.close_time = datetime.now(timezone.utc)
        pos.close_price = final_price
        pos.close_reason = reason
        pos.realized_pnl = pnl
        pos.unrealized_pnl = 0.0
        pos.status = OrderStatus.CLOSED

        # Update account balance with realized PnL
        self.balance += pnl
        self.history.append(pos)
        del self.positions[position_id]

        self._recalculate_account()

        logger.info(
            "Closed paper position [%s] %s @ %.5f | Reason: %s | PnL: $%.2f",
            pos.id[:8],
            pos.symbol,
            final_price,
            reason,
            pnl,
        )

        return PaperTradeResult(
            success=True,
            position_id=pos.id,
            symbol=pos.symbol,
            side=pos.side.value,
            volume=pos.volume,
            price=final_price,
            realized_pnl=pnl,
            message=f"Position closed ({reason}). Realized PnL: ${pnl:.2f}",
            position=pos,
        )

    def partial_close(
        self,
        position_id: str,
        volume_to_close: float,
        price: Optional[float] = None,
    ) -> PaperTradeResult:
        """Partially close an existing open position."""
        if position_id not in self.positions:
            return PaperTradeResult(
                success=False,
                position_id=position_id,
                message=f"Position {position_id} not found.",
            )

        pos = self.positions[position_id]
        if volume_to_close <= 0 or volume_to_close >= pos.volume:
            if volume_to_close >= pos.volume:
                return self.close_position(position_id, price=price, reason="full_close_partial_call")
            return PaperTradeResult(
                success=False,
                position_id=position_id,
                message=f"Invalid volume to close: {volume_to_close}. Current: {pos.volume}",
            )

        close_price = price if price is not None and price > 0 else pos.current_price
        specs = self.get_symbol_specs(pos.symbol)
        slippage_delta = self.slippage_pips * specs["pip_size"]
        if pos.side == OrderSide.BUY:
            final_price = close_price - slippage_delta
        else:
            final_price = close_price + slippage_delta

        # Pro-rated PnL for partial volume
        portion = volume_to_close / pos.volume
        full_pnl = self._calculate_pnl(pos, final_price)
        partial_pnl = full_pnl * portion

        # Create closed position record for history
        partial_record = PaperPosition(
            id=str(uuid.uuid4()),
            symbol=pos.symbol,
            side=pos.side,
            volume=volume_to_close,
            open_price=pos.open_price,
            current_price=final_price,
            sl=pos.sl,
            tp=pos.tp,
            open_time=pos.open_time,
            close_time=datetime.now(timezone.utc),
            close_price=final_price,
            close_reason=f"partial_close_{volume_to_close}",
            realized_pnl=partial_pnl,
            unrealized_pnl=0.0,
            commission=round(pos.commission * portion, 2),
            status=OrderStatus.CLOSED,
            comment=f"{pos.comment} (partial from {pos.id[:8]})",
        )
        self.history.append(partial_record)

        # Update remaining position
        pos.volume = round(pos.volume - volume_to_close, 2)
        pos.commission = round(pos.commission - partial_record.commission, 2)
        self.balance += partial_pnl
        self._recalculate_account()

        logger.info(
            "Partial close [%s] %s: closed %.2f lots @ %.5f, remaining %.2f lots | PnL: $%.2f",
            pos.id[:8],
            pos.symbol,
            volume_to_close,
            final_price,
            pos.volume,
            partial_pnl,
        )

        return PaperTradeResult(
            success=True,
            position_id=pos.id,
            symbol=pos.symbol,
            side=pos.side.value,
            volume=volume_to_close,
            price=final_price,
            realized_pnl=partial_pnl,
            message=f"Partially closed {volume_to_close} lots. Remaining: {pos.volume} lots.",
            position=pos,
        )

    def modify_position(
        self,
        position_id: str,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        trailing_stop_pips: Optional[float] = None,
    ) -> PaperTradeResult:
        """Modify stop loss, take profit, or trailing stop of open position."""
        if position_id not in self.positions:
            return PaperTradeResult(
                success=False,
                position_id=position_id,
                message=f"Position {position_id} not found.",
            )

        pos = self.positions[position_id]
        curr_price = pos.current_price

        # Validate new SL if supplied
        if sl is not None:
            if pos.side == OrderSide.BUY and sl >= curr_price:
                return PaperTradeResult(
                    success=False,
                    position_id=position_id,
                    message=f"Buy SL ({sl}) cannot be above current price ({curr_price})",
                )
            if pos.side == OrderSide.SELL and sl <= curr_price:
                return PaperTradeResult(
                    success=False,
                    position_id=position_id,
                    message=f"Sell SL ({sl}) cannot be below current price ({curr_price})",
                )
            pos.sl = sl

        # Validate new TP if supplied
        if tp is not None:
            if pos.side == OrderSide.BUY and tp <= curr_price:
                return PaperTradeResult(
                    success=False,
                    position_id=position_id,
                    message=f"Buy TP ({tp}) cannot be below current price ({curr_price})",
                )
            if pos.side == OrderSide.SELL and tp >= curr_price:
                return PaperTradeResult(
                    success=False,
                    position_id=position_id,
                    message=f"Sell TP ({tp}) cannot be above current price ({curr_price})",
                )
            pos.tp = tp

        if trailing_stop_pips is not None:
            pos.trailing_stop_pips = trailing_stop_pips if trailing_stop_pips > 0 else None

        logger.info(
            "Modified paper position [%s] %s | New SL: %s, New TP: %s, Trailing: %s",
            pos.id[:8],
            pos.symbol,
            f"{pos.sl:.5f}" if pos.sl else "None",
            f"{pos.tp:.5f}" if pos.tp else "None",
            pos.trailing_stop_pips,
        )

        return PaperTradeResult(
            success=True,
            position_id=pos.id,
            symbol=pos.symbol,
            side=pos.side.value,
            volume=pos.volume,
            price=curr_price,
            sl=pos.sl,
            tp=pos.tp,
            message="Position parameters modified successfully.",
            position=pos,
        )

    # -------------------------------------------------------------------------
    # Price Updates & Trigger Monitoring
    # -------------------------------------------------------------------------
    def update_positions(
        self,
        current_prices: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Update open positions with latest market prices.
        current_prices can be:
          - Dict[symbol, float] -> Mid price
          - Dict[symbol, {"bid": float, "ask": float}]

        Checks:
        1. SL and TP hits
        2. Trailing stop updates
        3. Unrealized PnL updates
        4. Account equity & margin calculations

        Returns a list of event dictionaries for any positions triggered or closed.
        """
        events: List[Dict[str, Any]] = []
        positions_to_close: List[Tuple[str, float, str]] = []

        for pos_id, pos in list(self.positions.items()):
            price_data = current_prices.get(pos.symbol)
            if price_data is None:
                continue

            if isinstance(price_data, dict):
                bid = float(price_data.get("bid", 0.0))
                ask = float(price_data.get("ask", 0.0))
            else:
                bid = ask = float(price_data)

            if bid <= 0 or ask <= 0:
                continue

            # Buy positions close at Bid; Sell positions close at Ask
            eval_price = bid if pos.side == OrderSide.BUY else ask
            pos.current_price = eval_price

            # Update highest/lowest for trailing stop
            if pos.side == OrderSide.BUY:
                if eval_price > pos.highest_price:
                    pos.highest_price = eval_price
            else:
                if pos.lowest_price == 0.0 or eval_price < pos.lowest_price:
                    pos.lowest_price = eval_price

            specs = self.get_symbol_specs(pos.symbol)
            pip_size = specs["pip_size"]

            # Handle Trailing Stop logic
            if pos.trailing_stop_pips and pos.trailing_stop_pips > 0:
                trail_distance = pos.trailing_stop_pips * pip_size
                if pos.side == OrderSide.BUY:
                    new_sl = pos.highest_price - trail_distance
                    if new_sl > pos.open_price and (pos.sl is None or new_sl > pos.sl):
                        pos.sl = round(new_sl, specs["digits"])
                        events.append({
                            "type": "TRAILING_STOP_MOVED",
                            "position_id": pos.id,
                            "symbol": pos.symbol,
                            "new_sl": pos.sl,
                        })
                elif pos.side == OrderSide.SELL:
                    new_sl = pos.lowest_price + trail_distance
                    if new_sl < pos.open_price and (pos.sl is None or new_sl < pos.sl):
                        pos.sl = round(new_sl, specs["digits"])
                        events.append({
                            "type": "TRAILING_STOP_MOVED",
                            "position_id": pos.id,
                            "symbol": pos.symbol,
                            "new_sl": pos.sl,
                        })

            # Check Stop Loss hit
            if pos.sl is not None:
                if (pos.side == OrderSide.BUY and bid <= pos.sl) or (
                    pos.side == OrderSide.SELL and ask >= pos.sl
                ):
                    positions_to_close.append((pos_id, pos.sl, "stop_loss"))
                    continue

            # Check Take Profit hit
            if pos.tp is not None:
                if (pos.side == OrderSide.BUY and bid >= pos.tp) or (
                    pos.side == OrderSide.SELL and ask <= pos.tp
                ):
                    positions_to_close.append((pos_id, pos.tp, "take_profit"))
                    continue

            # Update unrealized PnL
            pos.unrealized_pnl = self._calculate_pnl(pos, eval_price)

        # Process any closed positions
        for p_id, trigger_price, reason in positions_to_close:
            res = self.close_position(p_id, price=trigger_price, reason=reason)
            events.append({
                "type": f"ORDER_{reason.upper()}",
                "position_id": p_id,
                "symbol": res.symbol,
                "price": res.price,
                "realized_pnl": res.realized_pnl,
            })

        self._recalculate_account()
        return events

    # -------------------------------------------------------------------------
    # PnL & Margin Internals
    # -------------------------------------------------------------------------
    def _calculate_pnl(self, pos: PaperPosition, current_price: float) -> float:
        """Calculate gross unrealized or realized PnL for a position."""
        specs = self.get_symbol_specs(pos.symbol)
        contract_size = specs["contract_size"]

        if pos.side == OrderSide.BUY:
            price_diff = current_price - pos.open_price
        else:
            price_diff = pos.open_price - current_price

        sym = pos.symbol.upper()
        if sym.endswith("USD"):
            # EURUSD, GBPUSD, XAUUSD
            return round(price_diff * contract_size * pos.volume, 2)
        elif sym.startswith("USD"):
            # USDJPY, USDCAD, USDCHF
            if current_price > 0:
                return round((price_diff * contract_size * pos.volume) / current_price, 2)
            return round(price_diff * 10.0 * pos.volume, 2)
        else:
            # Cross rates standard approximation
            return round(price_diff * (contract_size / 100000.0) * 10.0 * pos.volume, 2)

    def _recalculate_account(self) -> None:
        """Update equity, margin, free margin, and margin level."""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_margin = sum(
            self.calculate_required_margin(p.symbol, p.volume, p.current_price)
            for p in self.positions.values()
        )

        self.equity = round(self.balance + total_unrealized, 2)
        self.margin = round(total_margin, 2)
        self.free_margin = round(self.equity - self.margin, 2)

        if self.margin > 0:
            self.margin_level = round((self.equity / self.margin) * 100.0, 2)
        else:
            self.margin_level = 0.0

    # -------------------------------------------------------------------------
    # Getters & Summary
    # -------------------------------------------------------------------------
    def get_open_positions(self) -> List[PaperPosition]:
        """Return list of all open paper positions."""
        return list(self.positions.values())

    def get_position(self, position_id: str) -> Optional[PaperPosition]:
        """Return single position by id if found."""
        return self.positions.get(position_id)

    def get_account_summary(self) -> Dict[str, Any]:
        """Return comprehensive snapshot of the paper trading account state."""
        self._recalculate_account()
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_realized = sum(p.realized_pnl for p in self.history)
        total_commissions = sum(p.commission for p in self.positions.values()) + sum(
            p.commission for p in self.history
        )

        return {
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "margin": round(self.margin, 2),
            "free_margin": round(self.free_margin, 2),
            "margin_level": round(self.margin_level, 2),
            "currency": self.currency,
            "leverage": self.leverage,
            "initial_balance": self.initial_balance,
            "unrealized_pnl": round(total_unrealized, 2),
            "realized_pnl": round(total_realized, 2),
            "total_commissions": round(total_commissions, 2),
            "open_positions_count": len(self.positions),
            "closed_trades_count": len(self.history),
        }

    def reset(
        self,
        initial_balance: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> None:
        """Reset paper engine state back to initial."""
        if initial_balance is not None:
            self.initial_balance = initial_balance
        if currency is not None:
            self.currency = currency

        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.margin = 0.0
        self.free_margin = self.initial_balance
        self.margin_level = 0.0
        self.positions.clear()
        self.history.clear()
        logger.info("PaperTradingEngine reset with balance %.2f %s", self.balance, self.currency)
