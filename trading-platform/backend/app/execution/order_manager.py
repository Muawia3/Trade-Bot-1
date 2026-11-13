"""
Order Manager.

Oversees lifecycle management of active positions and orders:
- Pending order tracking
- Open position monitoring
- Real-time trailing stop management
- Break-even triggers
- Position modifications (SL/TP)
- Partial position exits
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.core.config import get_settings
from app.core.constants import OrderSide, OrderStatus, OrderType
from app.core.logging_config import get_logger
from app.paper_trading.paper_engine import (
    PaperPosition,
    PaperTradeResult,
    PaperTradingEngine,
)

logger = get_logger("execution.order_manager")


@dataclass
class PendingOrder:
    """Represents a limit or stop pending order."""

    id: str
    symbol: str
    order_type: OrderType  # LIMIT or STOP
    side: OrderSide        # BUY or SELL
    volume: float
    target_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: OrderStatus = OrderStatus.PENDING
    comment: str = "Pending Order"
    magic_number: int = 100001

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "volume": self.volume,
            "target_price": round(self.target_price, 5),
            "stop_loss": round(self.stop_loss, 5) if self.stop_loss else None,
            "take_profit": round(self.take_profit, 5) if self.take_profit else None,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "comment": self.comment,
        }


class OrderManager:
    """
    Manages active orders and open positions across paper and live trading.
    Provides proactive risk management such as trailing stops, break-even adjustments,
    and partial profit takes.
    """

    def __init__(
        self,
        paper_engine: Optional[PaperTradingEngine] = None,
        notification_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self.settings = get_settings()
        self.paper_engine = paper_engine or PaperTradingEngine()
        self.notification_callback = notification_callback

        self.pending_orders: Dict[str, PendingOrder] = {}
        # Tracking for break-even state: {position_id: bool}
        self.break_even_activated: Dict[str, bool] = {}

        logger.info("OrderManager initialized.")

    # -------------------------------------------------------------------------
    # Pending Orders
    # -------------------------------------------------------------------------
    def place_pending_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        volume: float,
        target_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "Pending Order",
    ) -> PendingOrder:
        """Create and track a pending order."""
        order_id = str(uuid.uuid4())
        order = PendingOrder(
            id=order_id,
            symbol=symbol.upper(),
            order_type=order_type,
            side=side,
            volume=volume,
            target_price=target_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=comment,
        )
        self.pending_orders[order_id] = order
        logger.info(
            "Placed pending order [%s] %s %s %s %.2f lots @ %.5f",
            order_id[:8],
            symbol,
            order_type.value,
            side.value,
            volume,
            target_price,
        )
        return order

    def cancel_pending_order(self, order_id: str, reason: str = "user_cancelled") -> bool:
        """Cancel an existing pending order."""
        if order_id in self.pending_orders:
            order = self.pending_orders[order_id]
            order.status = OrderStatus.CANCELLED
            del self.pending_orders[order_id]
            logger.info("Cancelled pending order [%s]. Reason: %s", order_id[:8], reason)
            return True
        return False

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[PendingOrder]:
        """List all currently pending orders."""
        orders = list(self.pending_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol.upper() == symbol.upper()]
        return orders

    # -------------------------------------------------------------------------
    # Price Updates & Pending Order Triggering
    # -------------------------------------------------------------------------
    def check_pending_orders(self, current_prices: Dict[str, Any]) -> List[PendingOrder]:
        """
        Check if market prices have triggered any pending orders.
        Fills orders into open positions if triggered.
        """
        triggered: List[PendingOrder] = []

        for order_id, order in list(self.pending_orders.items()):
            price_data = current_prices.get(order.symbol)
            if price_data is None:
                continue

            if isinstance(price_data, dict):
                bid = float(price_data.get("bid", 0.0))
                ask = float(price_data.get("ask", 0.0))
            else:
                bid = ask = float(price_data)

            if bid <= 0 or ask <= 0:
                continue

            fill_price = ask if order.side == OrderSide.BUY else bid
            is_triggered = False

            # Limit Orders: Buy Limit executes when Ask <= Target; Sell Limit when Bid >= Target
            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and ask <= order.target_price:
                    is_triggered = True
                elif order.side == OrderSide.SELL and bid >= order.target_price:
                    is_triggered = True

            # Stop Orders: Buy Stop executes when Ask >= Target; Sell Stop when Bid <= Target
            elif order.order_type == OrderType.STOP:
                if order.side == OrderSide.BUY and ask >= order.target_price:
                    is_triggered = True
                elif order.side == OrderSide.SELL and bid <= order.target_price:
                    is_triggered = True

            if is_triggered:
                logger.info(
                    "Pending order triggered [%s] %s %s @ %.5f",
                    order.id[:8],
                    order.symbol,
                    order.side.value,
                    fill_price,
                )
                # Open position in paper engine
                self.paper_engine.open_position(
                    symbol=order.symbol,
                    side=order.side,
                    volume=order.volume,
                    price=fill_price,
                    sl=order.stop_loss,
                    tp=order.take_profit,
                    comment=f"Pending Fill: {order.comment}",
                )
                order.status = OrderStatus.FILLED
                triggered.append(order)
                del self.pending_orders[order_id]

        return triggered

    # -------------------------------------------------------------------------
    # Position Monitoring & Safety Rules
    # -------------------------------------------------------------------------
    def monitor_positions(
        self,
        current_prices: Dict[str, Any],
        break_even_pips: Optional[float] = 20.0,
    ) -> List[Dict[str, Any]]:
        """
        Synchronize positions with latest prices and apply:
        1. SL / TP hit evaluation via PaperTradingEngine
        2. Break-Even threshold automation (moves SL to open price + buffer)
        """
        # Let paper engine evaluate SL / TP hits and trailing stops
        events = self.paper_engine.update_positions(current_prices)

        # Check Break-Even trigger for remaining open positions
        if break_even_pips and break_even_pips > 0:
            for pos in self.paper_engine.get_open_positions():
                if self.break_even_activated.get(pos.id, False):
                    continue

                specs = self.paper_engine.get_symbol_specs(pos.symbol)
                pip_size = specs["pip_size"]
                curr_price = pos.current_price

                if pos.side == OrderSide.BUY:
                    profit_pips = (curr_price - pos.open_price) / pip_size
                    if profit_pips >= break_even_pips:
                        # Move SL to entry price + 1 pip buffer
                        new_sl = round(pos.open_price + (1.0 * pip_size), specs["digits"])
                        if pos.sl is None or new_sl > pos.sl:
                            pos.sl = new_sl
                            self.break_even_activated[pos.id] = True
                            event = {
                                "type": "BREAK_EVEN_TRIGGERED",
                                "position_id": pos.id,
                                "symbol": pos.symbol,
                                "new_sl": new_sl,
                            }
                            events.append(event)
                            logger.info(
                                "Break-even triggered for [%s] %s: moved SL to %.5f",
                                pos.id[:8],
                                pos.symbol,
                                new_sl,
                            )
                elif pos.side == OrderSide.SELL:
                    profit_pips = (pos.open_price - curr_price) / pip_size
                    if profit_pips >= break_even_pips:
                        # Move SL to entry price - 1 pip buffer
                        new_sl = round(pos.open_price - (1.0 * pip_size), specs["digits"])
                        if pos.sl is None or new_sl < pos.sl:
                            pos.sl = new_sl
                            self.break_even_activated[pos.id] = True
                            event = {
                                "type": "BREAK_EVEN_TRIGGERED",
                                "position_id": pos.id,
                                "symbol": pos.symbol,
                                "new_sl": new_sl,
                            }
                            events.append(event)
                            logger.info(
                                "Break-even triggered for [%s] %s: moved SL to %.5f",
                                pos.id[:8],
                                pos.symbol,
                                new_sl,
                            )

        # Notify callback if registered
        if self.notification_callback and events:
            for ev in events:
                self.notification_callback(ev["type"], ev)

        return events

    # -------------------------------------------------------------------------
    # Position Adjustments
    # -------------------------------------------------------------------------
    def modify_position(
        self,
        position_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_pips: Optional[float] = None,
    ) -> PaperTradeResult:
        """Modify open position parameters."""
        return self.paper_engine.modify_position(
            position_id=position_id,
            sl=stop_loss,
            tp=take_profit,
            trailing_stop_pips=trailing_stop_pips,
        )

    def close_position(
        self,
        position_id: str,
        price: Optional[float] = None,
        reason: str = "manual",
    ) -> PaperTradeResult:
        """Close an open position."""
        if position_id in self.break_even_activated:
            del self.break_even_activated[position_id]
        return self.paper_engine.close_position(position_id=position_id, price=price, reason=reason)

    def partial_close(
        self,
        position_id: str,
        volume_to_close: float,
        price: Optional[float] = None,
    ) -> PaperTradeResult:
        """Partially close an open position."""
        return self.paper_engine.partial_close(
            position_id=position_id,
            volume_to_close=volume_to_close,
            price=price,
        )

    def close_all_positions(self, symbol: Optional[str] = None) -> List[PaperTradeResult]:
        """Emergency action: Close all open positions immediately."""
        results: List[PaperTradeResult] = []
        positions = self.paper_engine.get_open_positions()

        for pos in positions:
            if symbol is None or pos.symbol.upper() == symbol.upper():
                res = self.close_position(pos.id, reason="emergency_close_all")
                results.append(res)

        logger.warning("Closed %d positions via close_all_positions.", len(results))
        return results

    def get_open_positions(self) -> List[PaperPosition]:
        """Return all open positions from engine."""
        return self.paper_engine.get_open_positions()
