"""
Backtest Execution Simulator.

Simulates order fills, slippage, bid/ask spreads, commissions, and intrabar
SL/TP price collisions without look-ahead bias.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.backtesting.performance_metrics import TradeRecord
from app.core.constants import OrderSide, OrderStatus
from app.core.logging_config import get_logger

logger = get_logger("backtesting.simulator")


@dataclass
class VirtualPosition:
    """Represents an active virtual position inside the backtest simulator."""

    id: str
    symbol: str
    side: OrderSide
    volume: float
    entry_price: float
    current_price: float
    sl: Optional[float]
    tp: Optional[float]
    entry_time: datetime
    entry_bar_idx: int
    commission: float = 0.0
    unrealized_pnl: float = 0.0


class BacktestSimulator:
    """
    Simulates high-precision order execution and intrabar trade resolution.

    Features:
    - Spread modeling (buys executed at Ask, sells executed at Bid)
    - Configurable adverse slippage
    - Fixed commission per standard lot
    - Pessimistic intrabar collision resolution (if both SL and TP fall inside [Low, High],
      Stop Loss is triggered to prevent look-ahead optimism)
    - Full bar-by-bar balance and equity curve tracking
    """

    def __init__(
        self,
        symbol: str,
        initial_balance: float = 10000.0,
        spread_pips: float = 1.5,
        slippage_pips: float = 0.3,
        commission_per_lot: float = 7.0,
        leverage: float = 100.0,
    ) -> None:
        self.symbol = symbol.upper()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.spread_pips = spread_pips
        self.slippage_pips = slippage_pips
        self.commission_per_lot = commission_per_lot
        self.leverage = leverage

        # Determine instrument specifications
        self.specs = self._determine_symbol_specs(self.symbol)
        self.pip_size = self.specs["pip_size"]
        self.contract_size = self.specs["contract_size"]

        self.open_positions: Dict[str, VirtualPosition] = {}
        self.closed_trades: List[TradeRecord] = []
        self.equity_curve: List[float] = [initial_balance]
        self.timestamps: List[datetime] = []

    @staticmethod
    def _determine_symbol_specs(symbol: str) -> Dict[str, Any]:
        sym = symbol.upper()
        if "XAU" in sym:
            return {"contract_size": 100.0, "pip_size": 0.01, "digits": 2}
        if "XAG" in sym:
            return {"contract_size": 5000.0, "pip_size": 0.001, "digits": 3}
        if "JPY" in sym:
            return {"contract_size": 100000.0, "pip_size": 0.01, "digits": 3}
        return {"contract_size": 100000.0, "pip_size": 0.0001, "digits": 5}

    def _calculate_pip_value(self, price: float, volume: float) -> float:
        """Calculate the USD pip value for the position."""
        if self.symbol.endswith("USD"):
            return self.contract_size * self.pip_size * volume
        elif self.symbol.startswith("USD"):
            return (self.contract_size * self.pip_size / price) * volume if price > 0 else 10.0 * volume
        return 10.0 * volume

    def calculate_pnl(
        self,
        side: OrderSide,
        open_price: float,
        close_price: float,
        volume: float,
    ) -> float:
        """Calculate gross trade PnL."""
        if side == OrderSide.BUY:
            price_diff = close_price - open_price
        else:
            price_diff = open_price - close_price

        if self.symbol.endswith("USD"):
            return price_diff * self.contract_size * volume
        elif self.symbol.startswith("USD"):
            return (price_diff * self.contract_size * volume) / close_price if close_price > 0 else price_diff * 10.0 * volume
        return price_diff * (self.contract_size / 100000.0) * 10.0 * volume

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------
    def open_order(
        self,
        side: OrderSide,
        volume: float,
        market_price: float,
        sl: Optional[float],
        tp: Optional[float],
        bar_idx: int,
        timestamp: datetime,
    ) -> Optional[VirtualPosition]:
        """
        Open a new virtual position.
        Applies spread and slippage.
        """
        if volume <= 0 or market_price <= 0:
            return None

        spread_offset = (self.spread_pips / 2.0) * self.pip_size
        slippage_offset = self.slippage_pips * self.pip_size

        if side == OrderSide.BUY:
            # Buy executes at Ask + slippage
            fill_price = market_price + spread_offset + slippage_offset
        else:
            # Sell executes at Bid - slippage
            fill_price = market_price - spread_offset - slippage_offset

        # Validate SL
        if sl is not None:
            if side == OrderSide.BUY and sl >= fill_price:
                sl = fill_price - (20.0 * self.pip_size)
            elif side == OrderSide.SELL and sl <= fill_price:
                sl = fill_price + (20.0 * self.pip_size)

        commission = self.commission_per_lot * volume
        self.balance -= commission

        pos_id = str(uuid.uuid4())
        pos = VirtualPosition(
            id=pos_id,
            symbol=self.symbol,
            side=side,
            volume=volume,
            entry_price=fill_price,
            current_price=fill_price,
            sl=sl,
            tp=tp,
            entry_time=timestamp,
            entry_bar_idx=bar_idx,
            commission=commission,
        )
        self.open_positions[pos_id] = pos
        return pos

    def close_order(
        self,
        position_id: str,
        market_price: float,
        timestamp: datetime,
        reason: str = "signal_exit",
    ) -> Optional[TradeRecord]:
        """Close an active virtual position."""
        if position_id not in self.open_positions:
            return None

        pos = self.open_positions[position_id]
        spread_offset = (self.spread_pips / 2.0) * self.pip_size
        slippage_offset = self.slippage_pips * self.pip_size

        if pos.side == OrderSide.BUY:
            exit_price = market_price - spread_offset - slippage_offset
        else:
            exit_price = market_price + spread_offset + slippage_offset

        gross_pnl = self.calculate_pnl(pos.side, pos.entry_price, exit_price, pos.volume)
        net_pnl = gross_pnl - pos.commission

        self.balance += gross_pnl

        record = TradeRecord(
            trade_id=pos.id,
            symbol=pos.symbol,
            side=pos.side.value,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            entry_price=round(pos.entry_price, 5),
            exit_price=round(exit_price, 5),
            volume=pos.volume,
            net_pnl=round(net_pnl, 2),
            gross_pnl=round(gross_pnl, 2),
            commission=round(pos.commission, 2),
            return_pct=round((net_pnl / self.initial_balance) * 100.0, 4),
            exit_reason=reason,
        )

        self.closed_trades.append(record)
        del self.open_positions[position_id]
        return record

    # -------------------------------------------------------------------------
    # Intrabar Evaluation
    # -------------------------------------------------------------------------
    def evaluate_bar(
        self,
        bar_idx: int,
        timestamp: datetime,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> List[TradeRecord]:
        """
        Evaluate SL and TP hits inside the current candle without look-ahead bias.

        Pessimistic Collision Rule:
        If both Stop Loss and Take Profit levels lie within [low_p, high_p],
        we assume the Stop Loss was hit first. This eliminates over-optimistic fills.
        """
        closed_this_bar: List[TradeRecord] = []
        spread_offset = (self.spread_pips / 2.0) * self.pip_size

        for pos_id, pos in list(self.open_positions.items()):
            sl_hit = False
            tp_hit = False

            if pos.side == OrderSide.BUY:
                # For BUY: SL evaluated at Bid (low - spread)
                bid_low = low_p - spread_offset
                bid_high = high_p - spread_offset

                if pos.sl is not None and bid_low <= pos.sl:
                    sl_hit = True
                if pos.tp is not None and bid_high >= pos.tp:
                    tp_hit = True

                if sl_hit and tp_hit:
                    # Intrabar collision -> assume SL hit
                    rec = self._execute_direct_exit(pos, pos.sl, timestamp, "stop_loss_collision")
                    closed_this_bar.append(rec)
                elif sl_hit:
                    rec = self._execute_direct_exit(pos, pos.sl, timestamp, "stop_loss")
                    closed_this_bar.append(rec)
                elif tp_hit:
                    rec = self._execute_direct_exit(pos, pos.tp, timestamp, "take_profit")
                    closed_this_bar.append(rec)
                else:
                    # Position remains open; update current price to Close Bid
                    pos.current_price = close_p - spread_offset
                    pos.unrealized_pnl = self.calculate_pnl(pos.side, pos.entry_price, pos.current_price, pos.volume)

            elif pos.side == OrderSide.SELL:
                # For SELL: SL evaluated at Ask (high + spread)
                ask_high = high_p + spread_offset
                ask_low = low_p + spread_offset

                if pos.sl is not None and ask_high >= pos.sl:
                    sl_hit = True
                if pos.tp is not None and ask_low <= pos.tp:
                    tp_hit = True

                if sl_hit and tp_hit:
                    # Intrabar collision -> assume SL hit
                    rec = self._execute_direct_exit(pos, pos.sl, timestamp, "stop_loss_collision")
                    closed_this_bar.append(rec)
                elif sl_hit:
                    rec = self._execute_direct_exit(pos, pos.sl, timestamp, "stop_loss")
                    closed_this_bar.append(rec)
                elif tp_hit:
                    rec = self._execute_direct_exit(pos, pos.tp, timestamp, "take_profit")
                    closed_this_bar.append(rec)
                else:
                    # Position remains open; update current price to Close Ask
                    pos.current_price = close_p + spread_offset
                    pos.unrealized_pnl = self.calculate_pnl(pos.side, pos.entry_price, pos.current_price, pos.volume)

        # Update equity snapshot
        total_unrealized = sum(p.unrealized_pnl for p in self.open_positions.values())
        self.equity = round(self.balance + total_unrealized, 2)
        self.equity_curve.append(self.equity)
        self.timestamps.append(timestamp)

        return closed_this_bar

    def _execute_direct_exit(
        self,
        pos: VirtualPosition,
        fill_price: float,
        timestamp: datetime,
        reason: str,
    ) -> TradeRecord:
        """Execute a direct SL or TP exit."""
        gross_pnl = self.calculate_pnl(pos.side, pos.entry_price, fill_price, pos.volume)
        net_pnl = gross_pnl - pos.commission

        self.balance += gross_pnl

        record = TradeRecord(
            trade_id=pos.id,
            symbol=pos.symbol,
            side=pos.side.value,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            entry_price=round(pos.entry_price, 5),
            exit_price=round(fill_price, 5),
            volume=pos.volume,
            net_pnl=round(net_pnl, 2),
            gross_pnl=round(gross_pnl, 2),
            commission=round(pos.commission, 2),
            return_pct=round((net_pnl / self.initial_balance) * 100.0, 4),
            exit_reason=reason,
        )

        self.closed_trades.append(record)
        del self.open_positions[pos.id]
        return record
