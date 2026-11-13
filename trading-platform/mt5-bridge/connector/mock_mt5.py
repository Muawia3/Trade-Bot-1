"""
Mock MetaTrader 5 module for testing and Linux/development environments.
Provides realistic simulated account info, symbol specifications, tick prices,
OHLCV historical candles, and order execution bookkeeping.
"""

import time
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd


# =============================================================================
# MetaTrader 5 Enumeration / Constant Mappings
# =============================================================================

# TimeFrames (minutes or equivalents matching MT5 standard constants)
TIMEFRAME_M1 = 1
TIMEFRAME_M2 = 2
TIMEFRAME_M3 = 3
TIMEFRAME_M4 = 4
TIMEFRAME_M5 = 5
TIMEFRAME_M6 = 6
TIMEFRAME_M10 = 10
TIMEFRAME_M12 = 12
TIMEFRAME_M15 = 15
TIMEFRAME_M20 = 20
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 60
TIMEFRAME_H2 = 120
TIMEFRAME_H3 = 180
TIMEFRAME_H4 = 240
TIMEFRAME_H6 = 360
TIMEFRAME_H8 = 480
TIMEFRAME_H12 = 720
TIMEFRAME_D1 = 1440
TIMEFRAME_W1 = 10080
TIMEFRAME_MN1 = 43200

# Order Types
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5
ORDER_TYPE_BUY_STOP_LIMIT = 6
ORDER_TYPE_SELL_STOP_LIMIT = 7

# Trade Actions
TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 5
TRADE_ACTION_SLTP = 6
TRADE_ACTION_MODIFY = 7
TRADE_ACTION_REMOVE = 8
TRADE_ACTION_CLOSE_BY = 10

# Return Codes
TRADE_RETCODE_REQUOTE = 10004
TRADE_RETCODE_REJECT = 10006
TRADE_RETCODE_CANCEL = 10007
TRADE_RETCODE_PLACED = 10008
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_DONE_PARTIAL = 10010
TRADE_RETCODE_ERROR = 10011
TRADE_RETCODE_TIMEOUT = 10012
TRADE_RETCODE_INVALID = 10013
TRADE_RETCODE_INVALID_VOLUME = 10014
TRADE_RETCODE_INVALID_PRICE = 10015
TRADE_RETCODE_INVALID_STOPS = 10016
TRADE_RETCODE_TRADE_DISABLED = 10017
TRADE_RETCODE_MARKET_CLOSED = 10018
TRADE_RETCODE_NO_MONEY = 10019
TRADE_RETCODE_PRICE_CHANGED = 10020
TRADE_RETCODE_PRICE_OFF = 10021
TRADE_RETCODE_INVALID_EXPIRATION = 10022
TRADE_RETCODE_ORDER_CHANGED = 10023
TRADE_RETCODE_TOO_MANY_REQUESTS = 10024
TRADE_RETCODE_NO_CHANGES = 10025
TRADE_RETCODE_SERVER_DISABLES_AT = 10026
TRADE_RETCODE_CLIENT_DISABLES_AT = 10027
TRADE_RETCODE_LOCKED = 10028
TRADE_RETCODE_FROZEN = 10029
TRADE_RETCODE_INVALID_FILL = 10030
TRADE_RETCODE_CONNECTION = 10031
TRADE_RETCODE_ONLY_REAL = 10032
TRADE_RETCODE_LIMIT_ORDERS = 10033
TRADE_RETCODE_LIMIT_VOLUME = 10034
TRADE_RETCODE_POSITION_CLOSED = 10035

# Trade Filling Modes
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2

# Trade Time Types
ORDER_TIME_GTC = 0
ORDER_TIME_DAY = 1
ORDER_TIME_SPECIFIED = 2
ORDER_TIME_SPECIFIED_DAY = 3

# Trade Execution Modes
SYMBOL_TRADE_MODE_DISABLED = 0
SYMBOL_TRADE_MODE_LONGONLY = 1
SYMBOL_TRADE_MODE_SHORTONLY = 2
SYMBOL_TRADE_MODE_CLOSEONLY = 3
SYMBOL_TRADE_MODE_FULL = 4


class MockAccountInfo:
    """Mock Account Information object simulating MT5 AccountInfo namedtuple."""

    def __init__(
        self,
        login: int = 12345678,
        trade_mode: int = 0,  # 0: demo, 1: contest, 2: real
        leverage: int = 100,
        limit_orders: int = 200,
        margin_so_mode: int = 0,
        trade_allowed: bool = True,
        trade_expert: bool = True,
        margin_mode: int = 0,
        currency_digits: int = 2,
        balance: float = 10000.0,
        credit: float = 0.0,
        profit: float = 0.0,
        equity: float = 10000.0,
        margin: float = 0.0,
        margin_free: float = 10000.0,
        margin_level: float = 0.0,
        margin_so_call: float = 50.0,
        margin_so_so: float = 30.0,
        margin_initial: float = 0.0,
        margin_maintenance: float = 0.0,
        assets: float = 0.0,
        liabilities: float = 0.0,
        commission_blocked: float = 0.0,
        name: str = "Mock Trading Account",
        server: str = "MetaQuotes-Demo",
        currency: str = "USD",
        company: str = "MetaQuotes Software Corp.",
    ):
        self.login = login
        self.trade_mode = trade_mode
        self.leverage = leverage
        self.limit_orders = limit_orders
        self.margin_so_mode = margin_so_mode
        self.trade_allowed = trade_allowed
        self.trade_expert = trade_expert
        self.margin_mode = margin_mode
        self.currency_digits = currency_digits
        self.balance = balance
        self.credit = credit
        self.profit = profit
        self.equity = equity
        self.margin = margin
        self.margin_free = margin_free
        self.margin_level = margin_level
        self.margin_so_call = margin_so_call
        self.margin_so_so = margin_so_so
        self.margin_initial = margin_initial
        self.margin_maintenance = margin_maintenance
        self.assets = assets
        self.liabilities = liabilities
        self.commission_blocked = commission_blocked
        self.name = name
        self.server = server
        self.currency = currency
        self.company = company

    def _asdict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class MockSymbolInfo:
    """Mock Symbol Information object simulating MT5 SymbolInfo namedtuple."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _asdict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class MockTick:
    """Mock Tick simulating MT5 Tick namedtuple."""

    def __init__(self, time_val: int, bid: float, ask: float, last: float, volume: int, flags: int = 6):
        self.time = time_val
        self.bid = bid
        self.ask = ask
        self.last = last
        self.volume = volume
        self.time_msc = int(time_val * 1000)
        self.flags = flags
        self.volume_real = float(volume)

    def _asdict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class MockOrderSendResult:
    """Mock order execution response simulating MT5 OrderSendResult."""

    def __init__(
        self,
        retcode: int = TRADE_RETCODE_DONE,
        deal: int = 1001,
        order: int = 2001,
        volume: float = 0.1,
        price: float = 0.0,
        bid: float = 0.0,
        ask: float = 0.0,
        comment: str = "Mock execution completed",
        request_id: int = 1,
        retcode_external: int = 0,
    ):
        self.retcode = retcode
        self.deal = deal
        self.order = order
        self.volume = volume
        self.price = price
        self.bid = bid
        self.ask = ask
        self.comment = comment
        self.request_id = request_id
        self.retcode_external = retcode_external

    def _asdict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class MockPosition:
    """Mock Position simulating MT5 TradePosition."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _asdict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class MockMT5Client:
    """
    In-memory stateful Mock MT5 terminal engine for testing and simulation.
    Maintains realistic account balance, equity, positions, orders, and tick/candle history.
    """

    def __init__(self):
        self._connected: bool = False
        self._last_error: Tuple[int, str] = (1, "Success")
        self._ticket_counter: int = 100000

        # Initial account specifications
        self._account = MockAccountInfo(
            login=99887766,
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            margin_free=10000.0,
            currency="USD",
            leverage=100,
            name="Mock Trader Pro",
            server="Mock-Demo-Server",
            company="Antigravity Forex Mock",
        )

        # Base prices for realistic simulation
        self._base_prices: Dict[str, Dict[str, Any]] = {
            "XAUUSD": {
                "bid": 2350.25,
                "ask": 2350.55,
                "digits": 2,
                "point": 0.01,
                "contract_size": 100.0,
                "tick_size": 0.01,
                "tick_value": 1.0,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
                "stops_level": 10,
                "freeze_level": 5,
                "spread": 30,
            },
            "EURUSD": {
                "bid": 1.08500,
                "ask": 1.08515,
                "digits": 5,
                "point": 0.00001,
                "contract_size": 100000.0,
                "tick_size": 0.00001,
                "tick_value": 1.0,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
                "stops_level": 15,
                "freeze_level": 5,
                "spread": 15,
            },
            "GBPUSD": {
                "bid": 1.27210,
                "ask": 1.27228,
                "digits": 5,
                "point": 0.00001,
                "contract_size": 100000.0,
                "tick_size": 0.00001,
                "tick_value": 1.0,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
                "stops_level": 15,
                "freeze_level": 5,
                "spread": 18,
            },
            "USDJPY": {
                "bid": 155.450,
                "ask": 155.465,
                "digits": 3,
                "point": 0.001,
                "contract_size": 100000.0,
                "tick_size": 0.001,
                "tick_value": 0.64,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
                "stops_level": 15,
                "freeze_level": 5,
                "spread": 15,
            },
        }

        # Active positions and orders
        self._positions: Dict[int, MockPosition] = {}
        self._orders: Dict[int, Dict[str, Any]] = {}
        self._trade_history: List[Dict[str, Any]] = []

    def initialize(
        self,
        path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        timeout: int = 60000,
        portable: bool = False,
    ) -> bool:
        """Simulate terminal initialization."""
        self._connected = True
        self._last_error = (1, "Success")
        if login:
            self._account.login = login
        if server:
            self._account.server = server
        return True

    def shutdown(self) -> None:
        """Simulate terminal shutdown."""
        self._connected = False

    def is_connected(self) -> bool:
        """Return connectivity status."""
        return self._connected

    def last_error(self) -> Tuple[int, str]:
        """Return last error tuple."""
        return self._last_error

    def account_info(self) -> Optional[MockAccountInfo]:
        """Return current simulated account information."""
        if not self._connected:
            self._last_error = (-10001, "Terminal not connected")
            return None
        self._recalculate_account()
        return self._account

    def symbols_total(self) -> int:
        """Return total available symbols."""
        return len(self._base_prices)

    def symbols_get(self, group: Optional[str] = None) -> List[MockSymbolInfo]:
        """Return list of symbols."""
        if not self._connected:
            return []
        symbols = []
        for sym in self._base_prices:
            if group and group.lower() not in sym.lower():
                continue
            info = self.symbol_info(sym)
            if info:
                symbols.append(info)
        return symbols

    def symbol_info(self, symbol: str) -> Optional[MockSymbolInfo]:
        """Return SymbolInfo for given symbol (handles normalized or broker-suffixed names)."""
        if not self._connected:
            return None

        clean_symbol = symbol.strip().upper()
        # Find matching base
        matched_base = None
        for base in self._base_prices:
            if base in clean_symbol:
                matched_base = base
                break

        if not matched_base:
            matched_base = "EURUSD"  # Default fallback if unknown

        data = self._base_prices[matched_base]
        # Introduce micro-fluctuations to tick
        jitter = random.uniform(-0.0002, 0.0002) * (100.0 if "XAU" in clean_symbol or "JPY" in clean_symbol else 1.0)
        bid = round(data["bid"] + jitter, data["digits"])
        spread_val = data["spread"] * data["point"]
        ask = round(bid + spread_val, data["digits"])

        return MockSymbolInfo(
            name=symbol,
            visible=True,
            select=True,
            digits=data["digits"],
            point=data["point"],
            spread=data["spread"],
            trade_mode=SYMBOL_TRADE_MODE_FULL,
            trade_contract_size=data["contract_size"],
            trade_tick_size=data["tick_size"],
            trade_tick_value=data["tick_value"],
            volume_min=data["volume_min"],
            volume_max=data["volume_max"],
            volume_step=data["volume_step"],
            trade_stops_level=data["stops_level"],
            trade_freeze_level=data["freeze_level"],
            bid=bid,
            ask=ask,
            last=bid,
            time=int(time.time()),
            currency_base=matched_base[:3],
            currency_profit="USD",
            currency_margin="USD",
        )

    def symbol_info_tick(self, symbol: str) -> Optional[MockTick]:
        """Return current simulated tick for symbol."""
        if not self._connected:
            return None
        info = self.symbol_info(symbol)
        if not info:
            return None
        return MockTick(
            time_val=int(time.time()),
            bid=info.bid,
            ask=info.ask,
            last=info.bid,
            volume=random.randint(1, 20),
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Optional[np.ndarray]:
        """
        Return numpy structured array of rates simulating MT5 copy_rates_from_pos.
        Timeframes in minutes.
        """
        if not self._connected or count <= 0:
            return None

        clean_symbol = symbol.strip().upper()
        matched_base = "XAUUSD" if "XAU" in clean_symbol else "EURUSD"
        base_data = self._base_prices.get(matched_base, self._base_prices["EURUSD"])
        digits = base_data["digits"]

        # Calculate interval in seconds
        interval_secs = timeframe * 60
        now = int(time.time())
        # Snap to timeframe boundary
        end_time = (now // interval_secs) * interval_secs

        times = [end_time - (count - 1 - i + start_pos) * interval_secs for i in range(count)]
        
        # Generate realistic random walk
        volatility = 0.0008 if "EUR" in clean_symbol else 0.50
        current_price = base_data["bid"]

        records = []
        for t in times:
            change = np.random.normal(0, volatility)
            open_p = round(current_price, digits)
            close_p = round(open_p + change, digits)
            high_p = round(max(open_p, close_p) + abs(np.random.normal(0, volatility * 0.5)), digits)
            low_p = round(min(open_p, close_p) - abs(np.random.normal(0, volatility * 0.5)), digits)
            tick_volume = int(max(10, np.random.normal(120, 40)))
            spread = base_data["spread"]
            real_volume = tick_volume * 10

            records.append((t, open_p, high_p, low_p, close_p, tick_volume, spread, real_volume))
            current_price = close_p

        dtype = [
            ("time", "<i8"),
            ("open", "<f8"),
            ("high", "<f8"),
            ("low", "<f8"),
            ("close", "<f8"),
            ("tick_volume", "<u8"),
            ("spread", "<i4"),
            ("real_volume", "<u8"),
        ]
        return np.array(records, dtype=dtype)

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: datetime, date_to: datetime
    ) -> Optional[np.ndarray]:
        """Simulate copy_rates_range between datetime objects."""
        if not self._connected:
            return None
        t_from = int(date_from.timestamp())
        t_to = int(date_to.timestamp())
        interval_secs = timeframe * 60
        if t_to <= t_from or interval_secs <= 0:
            return None

        count = max(1, (t_to - t_from) // interval_secs)
        # Cap count to 10000 for safety in mock
        count = min(count, 10000)
        return self.copy_rates_from_pos(symbol, timeframe, 0, count)

    def order_send(self, request: Dict[str, Any]) -> MockOrderSendResult:
        """
        Execute order send request in mock mode.
        Validates request parameters and updates mock positions/history.
        """
        if not self._connected:
            self._last_error = (-10001, "Terminal not connected")
            return MockOrderSendResult(retcode=TRADE_RETCODE_CONNECTION, comment="Terminal not connected")

        symbol = request.get("symbol", "EURUSD")
        action = request.get("action", TRADE_ACTION_DEAL)
        order_type = request.get("type", ORDER_TYPE_BUY)
        volume = float(request.get("volume", 0.01))
        price = float(request.get("price", 0.0))
        sl = float(request.get("sl", 0.0))
        tp = float(request.get("tp", 0.0))
        comment = request.get("comment", "Automated Mock Order")

        tick = self.symbol_info_tick(symbol)
        current_bid = tick.bid if tick else 1.08500
        current_ask = tick.ask if tick else 1.08515

        if action == TRADE_ACTION_DEAL:
            self._ticket_counter += 1
            ticket = self._ticket_counter
            fill_price = current_ask if order_type == ORDER_TYPE_BUY else current_bid

            pos = MockPosition(
                ticket=ticket,
                time=int(time.time()),
                time_msc=int(time.time() * 1000),
                time_update=int(time.time()),
                time_update_msc=int(time.time() * 1000),
                type=order_type,
                magic=request.get("magic", 1001),
                identifier=ticket,
                reason=3,
                volume=volume,
                price_open=fill_price,
                sl=sl,
                tp=tp,
                price_current=fill_price,
                swap=0.0,
                profit=0.0,
                symbol=symbol,
                comment=comment,
            )
            self._positions[ticket] = pos

            # Record in trade history
            self._trade_history.append({
                "ticket": ticket,
                "deal": ticket + 500000,
                "symbol": symbol,
                "type": "BUY" if order_type == ORDER_TYPE_BUY else "SELL",
                "volume": volume,
                "price": fill_price,
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "OPEN",
                "profit": 0.0,
                "comment": comment,
            })

            self._recalculate_account()
            return MockOrderSendResult(
                retcode=TRADE_RETCODE_DONE,
                deal=ticket + 500000,
                order=ticket,
                volume=volume,
                price=fill_price,
                bid=current_bid,
                ask=current_ask,
                comment="Mock deal executed successfully",
            )

        elif action == TRADE_ACTION_SLTP:
            position_id = request.get("position")
            if position_id in self._positions:
                pos = self._positions[position_id]
                pos.sl = sl
                pos.tp = tp
                pos.time_update = int(time.time())
                return MockOrderSendResult(retcode=TRADE_RETCODE_DONE, order=position_id, comment="SL/TP modified")
            return MockOrderSendResult(retcode=TRADE_RETCODE_REJECT, comment="Position not found")

        elif action == TRADE_ACTION_REMOVE:
            order_id = request.get("order")
            if order_id in self._orders:
                del self._orders[order_id]
                return MockOrderSendResult(retcode=TRADE_RETCODE_DONE, order=order_id, comment="Order removed")
            return MockOrderSendResult(retcode=TRADE_RETCODE_REJECT, comment="Order not found")

        return MockOrderSendResult(retcode=TRADE_RETCODE_DONE, comment="Mock action processed")

    def positions_get(self, symbol: Optional[str] = None, ticket: Optional[int] = None) -> List[MockPosition]:
        """Return list of active mock positions."""
        if not self._connected:
            return []
        self._recalculate_account()
        positions = list(self._positions.values())
        if ticket is not None:
            positions = [p for p in positions if p.ticket == ticket]
        if symbol is not None:
            positions = [p for p in positions if p.symbol.upper() == symbol.upper()]
        return positions

    def orders_get(self, symbol: Optional[str] = None, ticket: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return pending orders."""
        if not self._connected:
            return []
        orders = list(self._orders.values())
        if ticket is not None:
            orders = [o for o in orders if o.get("ticket") == ticket]
        if symbol is not None:
            orders = [o for o in orders if o.get("symbol", "").upper() == symbol.upper()]
        return orders

    def close_mock_position(self, ticket: int, volume: Optional[float] = None) -> MockOrderSendResult:
        """Close an active mock position."""
        if ticket not in self._positions:
            return MockOrderSendResult(retcode=TRADE_RETCODE_POSITION_CLOSED, comment="Position not found or closed")

        pos = self._positions[ticket]
        close_volume = volume if volume and volume < pos.volume else pos.volume

        tick = self.symbol_info_tick(pos.symbol)
        close_price = tick.bid if pos.type == ORDER_TYPE_BUY else tick.ask

        # Calculate final profit
        sym_info = self.symbol_info(pos.symbol)
        multiplier = sym_info.trade_contract_size if sym_info else 100.0
        pnl = (close_price - pos.price_open) if pos.type == ORDER_TYPE_BUY else (pos.price_open - close_price)
        realized_profit = round(pnl * close_volume * multiplier, 2)

        # Update balance
        self._account.balance += realized_profit

        if close_volume >= pos.volume:
            del self._positions[ticket]
        else:
            pos.volume -= close_volume

        self._trade_history.append({
            "ticket": ticket,
            "deal": ticket + 900000,
            "symbol": pos.symbol,
            "type": "SELL" if pos.type == ORDER_TYPE_BUY else "BUY",
            "volume": close_volume,
            "price": close_price,
            "time": datetime.now(timezone.utc).isoformat(),
            "action": "CLOSE",
            "profit": realized_profit,
            "comment": "Mock position closed",
        })

        self._recalculate_account()
        return MockOrderSendResult(
            retcode=TRADE_RETCODE_DONE,
            deal=ticket + 900000,
            order=ticket,
            volume=close_volume,
            price=close_price,
            comment=f"Closed with profit {realized_profit} USD",
        )

    def history_deals_get(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        group: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return simulated trade history."""
        return self._trade_history

    def order_calc_margin(self, action: int, symbol: str, volume: float, price: float) -> Optional[float]:
        """Calculate margin required for trade."""
        sym_info = self.symbol_info(symbol)
        if not sym_info:
            return None
        leverage = self._account.leverage or 100
        contract_size = sym_info.trade_contract_size
        return round((volume * contract_size * price) / leverage, 2)

    def _recalculate_account(self) -> None:
        """Update floating profit, equity, and margin for all positions."""
        total_profit = 0.0
        total_margin = 0.0

        for pos in self._positions.values():
            tick = self.symbol_info_tick(pos.symbol)
            if not tick:
                continue
            cur_price = tick.bid if pos.type == ORDER_TYPE_BUY else tick.ask
            pos.price_current = cur_price
            sym_info = self.symbol_info(pos.symbol)
            contract_size = sym_info.trade_contract_size if sym_info else 100.0

            pnl = (cur_price - pos.price_open) if pos.type == ORDER_TYPE_BUY else (pos.price_open - cur_price)
            pos_profit = pnl * pos.volume * contract_size
            pos.profit = round(pos_profit, 2)
            total_profit += pos.profit

            # Margin requirement
            req_margin = (pos.volume * contract_size * pos.price_open) / (self._account.leverage or 100)
            total_margin += req_margin

        self._account.profit = round(total_profit, 2)
        self._account.margin = round(total_margin, 2)
        self._account.equity = round(self._account.balance + total_profit, 2)
        self._account.margin_free = round(self._account.equity - self._account.margin, 2)
        if self._account.margin > 0:
            self._account.margin_level = round((self._account.equity / self._account.margin) * 100, 2)
        else:
            self._account.margin_level = 0.0


# Singleton mock instance
mock_mt5_instance = MockMT5Client()
