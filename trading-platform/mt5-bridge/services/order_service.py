"""
Order Execution and Position Management Service.
Enforces multi-layer safety verification, stop loss / take profit distance validation,
margin pre-checks, position modifications, and strict paper trading sandboxing.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union

try:
    from config.bridge_config import get_bridge_config, BridgeConfig, TradingMode
    from connector.mt5_connector import mt5_manager, mt5, _MT5_AVAILABLE
    from connector.mock_mt5 import (
        mock_mt5_instance,
        TRADE_ACTION_DEAL,
        TRADE_ACTION_SLTP,
        TRADE_RETCODE_DONE,
        ORDER_TYPE_BUY,
        ORDER_TYPE_SELL,
        ORDER_TIME_GTC,
        ORDER_FILLING_IOC,
    )
    from services.symbol_service import symbol_service, SymbolInfo
except ImportError:
    from mt5_bridge.config.bridge_config import get_bridge_config, BridgeConfig, TradingMode
    from mt5_bridge.connector.mt5_connector import mt5_manager, mt5, _MT5_AVAILABLE
    from mt5_bridge.connector.mock_mt5 import (
        mock_mt5_instance,
        TRADE_ACTION_DEAL,
        TRADE_ACTION_SLTP,
        TRADE_RETCODE_DONE,
        ORDER_TYPE_BUY,
        ORDER_TYPE_SELL,
        ORDER_TIME_GTC,
        ORDER_FILLING_IOC,
    )
    from mt5_bridge.services.symbol_service import symbol_service, SymbolInfo

logger = logging.getLogger("mt5_bridge.order_service")


@dataclass
class ValidationResult:
    """Result of order parameter validation."""
    is_valid: bool
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderResult:
    """Comprehensive result of order execution."""
    success: bool
    ticket: Optional[int] = None
    deal_id: Optional[int] = None
    symbol: str = ""
    side: str = ""
    volume: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    retcode: int = 0
    comment: str = ""
    timestamp: str = ""
    is_paper: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModifyResult:
    """Result of modifying stop loss or take profit."""
    success: bool
    ticket: int
    sl: float
    tp: float
    retcode: int
    comment: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CloseResult:
    """Result of closing an open position."""
    success: bool
    ticket: int
    closed_volume: float
    close_price: float
    realized_pnl: float
    retcode: int
    comment: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarginCheck:
    """Margin requirement assessment."""
    has_sufficient_margin: bool
    required_margin: float
    free_margin: float
    margin_level_after: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OrderService:
    """
    Core order execution engine with strict guardrails against unintended live trading.
    """

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or get_bridge_config()

    def check_margin(self, symbol: str, volume: float, side: str) -> MarginCheck:
        """
        Verify if account has adequate free margin to cover requested trade.
        """
        acc = mt5_manager.get_account_info_sync()
        if not acc:
            return MarginCheck(
                has_sufficient_margin=False,
                required_margin=0.0,
                free_margin=0.0,
                margin_level_after=0.0,
                error="Account info unavailable",
            )

        sym_info = symbol_service.get_symbol_info(symbol)
        if not sym_info:
            return MarginCheck(
                has_sufficient_margin=False,
                required_margin=0.0,
                free_margin=acc.get("free_margin", 0.0),
                margin_level_after=0.0,
                error=f"Symbol info unavailable for {symbol}",
            )

        # Get current approximate price
        tick = None
        if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
            tick = mock_mt5_instance.symbol_info_tick(sym_info.name)
        else:
            tick = mt5.symbol_info_tick(sym_info.name)

        ref_price = tick.ask if side.upper() == "BUY" else tick.bid if tick else 1.0
        leverage = acc.get("leverage", 100) or 100
        contract_size = sym_info.contract_size

        required_margin = (volume * contract_size * ref_price) / leverage
        free_margin = acc.get("free_margin", 0.0)
        current_equity = acc.get("equity", 0.0)
        current_margin = acc.get("margin", 0.0)

        new_total_margin = current_margin + required_margin
        new_margin_level = (current_equity / new_total_margin * 100.0) if new_total_margin > 0 else 0.0

        has_margin = free_margin >= required_margin
        return MarginCheck(
            has_sufficient_margin=has_margin,
            required_margin=round(required_margin, 2),
            free_margin=round(free_margin, 2),
            margin_level_after=round(new_margin_level, 2),
            error=None if has_margin else f"Insufficient margin: required {required_margin:.2f}, free {free_margin:.2f}",
        )

    def validate_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> ValidationResult:
        """
        Comprehensive pre-trade validation:
        - Symbol tradability
        - Volume min/max/step bounds
        - Stop loss & Take profit minimum distance (stops_level)
        - Margin sufficiency
        """
        sym_info = symbol_service.get_symbol_info(symbol)
        if not sym_info:
            return ValidationResult(is_valid=False, error_message=f"Unknown or unavailable symbol: {symbol}")

        if not sym_info.is_tradable:
            return ValidationResult(is_valid=False, error_message=f"Trading is disabled for symbol: {symbol}")

        side_clean = side.upper()
        if side_clean not in ("BUY", "SELL"):
            return ValidationResult(is_valid=False, error_message=f"Invalid side '{side}'. Must be BUY or SELL.")

        # Volume validation
        if volume < sym_info.volume_min:
            return ValidationResult(
                is_valid=False,
                error_message=f"Volume {volume} below minimum allowed {sym_info.volume_min}",
            )
        if volume > sym_info.volume_max:
            return ValidationResult(
                is_valid=False,
                error_message=f"Volume {volume} exceeds maximum allowed {sym_info.volume_max}",
            )

        # Check volume step
        step = sym_info.volume_step
        if step > 0:
            remainder = round((volume - sym_info.volume_min) % step, 6)
            if remainder != 0.0 and abs(remainder - step) > 1e-5:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Volume {volume} does not match required volume step of {step}",
                )

        # Validate SL / TP distances against broker stops_level
        stops_distance = sym_info.stops_level * sym_info.point
        if price is not None and price > 0:
            if sl is not None and sl > 0:
                if side_clean == "BUY":
                    if sl >= price:
                        return ValidationResult(is_valid=False, error_message=f"BUY SL ({sl}) must be below price ({price})")
                    if (price - sl) < stops_distance:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"BUY SL too close to market. Min distance is {stops_distance:.5f}",
                        )
                elif side_clean == "SELL":
                    if sl <= price:
                        return ValidationResult(is_valid=False, error_message=f"SELL SL ({sl}) must be above price ({price})")
                    if (sl - price) < stops_distance:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"SELL SL too close to market. Min distance is {stops_distance:.5f}",
                        )

            if tp is not None and tp > 0:
                if side_clean == "BUY":
                    if tp <= price:
                        return ValidationResult(is_valid=False, error_message=f"BUY TP ({tp}) must be above price ({price})")
                    if (tp - price) < stops_distance:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"BUY TP too close to market. Min distance is {stops_distance:.5f}",
                        )
                elif side_clean == "SELL":
                    if tp >= price:
                        return ValidationResult(is_valid=False, error_message=f"SELL TP ({tp}) must be below price ({price})")
                    if (price - tp) < stops_distance:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"SELL TP too close to market. Min distance is {stops_distance:.5f}",
                        )

        # Margin check
        margin_status = self.check_margin(symbol, volume, side_clean)
        if not margin_status.has_sufficient_margin:
            return ValidationResult(
                is_valid=False,
                error_message=margin_status.error or "Insufficient account margin",
                details=margin_status.to_dict(),
            )

        return ValidationResult(is_valid=True, details={"symbol": sym_info.name, "volume": volume})

    def send_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        order_type: str = "market",
        deviation: int = 20,
        comment: str = "AI Strategy Order",
        magic: int = 888888,
    ) -> OrderResult:
        """
        Execute an order.
        SAFETY ENFORCEMENT:
        If config.TRADING_MODE is PAPER or LIVE_TRADING_ENABLED is False, orders NEVER touch MT5 live execution.
        """
        side_clean = side.upper()
        sym_info = symbol_service.get_symbol_info(symbol)
        resolved_symbol = sym_info.name if sym_info else symbol

        # Current market price check
        tick = None
        if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
            tick = mock_mt5_instance.symbol_info_tick(resolved_symbol)
        else:
            tick = mt5.symbol_info_tick(resolved_symbol)

        market_price = (tick.ask if side_clean == "BUY" else tick.bid) if tick else price or 0.0
        exec_price = price if (price is not None and price > 0) else market_price

        # Step 1: Pre-validation
        val = self.validate_order(resolved_symbol, side_clean, volume, exec_price, sl, tp)
        if not val.is_valid:
            logger.warning("Order validation failed for %s %s: %s", side_clean, resolved_symbol, val.error_message)
            return OrderResult(
                success=False,
                symbol=resolved_symbol,
                side=side_clean,
                volume=volume,
                retcode=10013,
                comment=val.error_message or "Order validation failed",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Step 2: Safety Check - Paper Trading Isolation
        is_paper = self.config.is_paper_mode or mt5_manager.is_mock_mode

        if is_paper:
            logger.info("Executing in PAPER / SIMULATION mode: %s %s %.2f lots at %.5f", side_clean, resolved_symbol, volume, exec_price)
            mt5_order_type = ORDER_TYPE_BUY if side_clean == "BUY" else ORDER_TYPE_SELL
            req = {
                "action": TRADE_ACTION_DEAL,
                "symbol": resolved_symbol,
                "volume": volume,
                "type": mt5_order_type,
                "price": exec_price,
                "sl": sl or 0.0,
                "tp": tp or 0.0,
                "deviation": deviation,
                "magic": magic,
                "comment": f"[PAPER] {comment}",
            }
            res = mock_mt5_instance.order_send(req)
            success = (res.retcode == TRADE_RETCODE_DONE)
            return OrderResult(
                success=success,
                ticket=res.order,
                deal_id=res.deal,
                symbol=resolved_symbol,
                side=side_clean,
                volume=volume,
                price=res.price,
                sl=sl or 0.0,
                tp=tp or 0.0,
                retcode=res.retcode,
                comment=f"[PAPER] {res.comment}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_paper=True,
            )

        # Step 3: Real MT5 Terminal Execution (LIVE MODE ONLY)
        if not self.config.is_live_mode:
            logger.critical("SECURITY GUARD: Live trading blocked because LIVE_TRADING_ENABLED is False!")
            return OrderResult(
                success=False,
                symbol=resolved_symbol,
                side=side_clean,
                volume=volume,
                retcode=10017,
                comment="Live trading disabled by security configuration",
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_paper=False,
            )

        logger.warning("CRITICAL: Executing REAL LIVE order on MT5 terminal: %s %s %.2f lots", side_clean, resolved_symbol, volume)
        try:
            mt5_order_type = mt5.ORDER_TYPE_BUY if side_clean == "BUY" else mt5.ORDER_TYPE_SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": resolved_symbol,
                "volume": float(volume),
                "type": mt5_order_type,
                "price": float(exec_price),
                "sl": float(sl or 0.0),
                "tp": float(tp or 0.0),
                "deviation": deviation,
                "magic": magic,
                "comment": comment[:31],  # MT5 max 31 chars
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result is None:
                err_code, err_msg = mt5.last_error()
                logger.error("MT5 order_send returned None! Code: %s, Message: %s", err_code, err_msg)
                return OrderResult(
                    success=False,
                    symbol=resolved_symbol,
                    side=side_clean,
                    volume=volume,
                    retcode=err_code,
                    comment=f"MT5 API error: {err_msg}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    is_paper=False,
                )

            success = (result.retcode == mt5.TRADE_RETCODE_DONE)
            if not success:
                logger.error("MT5 order rejected with retcode %s: %s", result.retcode, result.comment)

            return OrderResult(
                success=success,
                ticket=result.order,
                deal_id=result.deal,
                symbol=resolved_symbol,
                side=side_clean,
                volume=result.volume,
                price=result.price,
                sl=sl or 0.0,
                tp=tp or 0.0,
                retcode=result.retcode,
                comment=result.comment,
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_paper=False,
            )

        except Exception as e:
            logger.exception("Exception during MT5 order execution: %s", e)
            return OrderResult(
                success=False,
                symbol=resolved_symbol,
                side=side_clean,
                volume=volume,
                retcode=10011,
                comment=f"Internal exception: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_paper=False,
            )

    def modify_position(self, ticket: int, sl: float, tp: float) -> ModifyResult:
        """
        Modify Stop Loss and Take Profit of open position.
        """
        if self.config.is_paper_mode or mt5_manager.is_mock_mode:
            req = {"action": TRADE_ACTION_SLTP, "position": ticket, "sl": sl, "tp": tp}
            res = mock_mt5_instance.order_send(req)
            return ModifyResult(
                success=(res.retcode == TRADE_RETCODE_DONE),
                ticket=ticket,
                sl=sl,
                tp=tp,
                retcode=res.retcode,
                comment=res.comment,
            )

        if not _MT5_AVAILABLE or mt5 is None:
            return ModifyResult(success=False, ticket=ticket, sl=sl, tp=tp, retcode=10031, comment="MT5 not available")

        # Live modification
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": float(sl),
            "tp": float(tp),
        }
        res = mt5.order_send(request)
        if res is None:
            err = mt5.last_error()
            return ModifyResult(success=False, ticket=ticket, sl=sl, tp=tp, retcode=err[0], comment=err[1])

        return ModifyResult(
            success=(res.retcode == mt5.TRADE_RETCODE_DONE),
            ticket=ticket,
            sl=sl,
            tp=tp,
            retcode=res.retcode,
            comment=res.comment,
        )

    def close_position(self, ticket: int, volume: Optional[float] = None) -> CloseResult:
        """
        Close position entirely or partially.
        """
        if self.config.is_paper_mode or mt5_manager.is_mock_mode:
            res = mock_mt5_instance.close_mock_position(ticket, volume)
            return CloseResult(
                success=(res.retcode == TRADE_RETCODE_DONE),
                ticket=ticket,
                closed_volume=res.volume,
                close_price=res.price,
                realized_pnl=0.0,
                retcode=res.retcode,
                comment=res.comment,
            )

        if not _MT5_AVAILABLE or mt5 is None:
            return CloseResult(success=False, ticket=ticket, closed_volume=0.0, close_price=0.0, realized_pnl=0.0, retcode=10031, comment="MT5 not available")

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return CloseResult(success=False, ticket=ticket, closed_volume=0.0, close_price=0.0, realized_pnl=0.0, retcode=10035, comment="Position not found")

        pos = positions[0]
        close_vol = volume if volume and volume < pos.volume else pos.volume
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return CloseResult(success=False, ticket=ticket, closed_volume=0.0, close_price=0.0, realized_pnl=0.0, retcode=10018, comment="Cannot obtain current price tick")

        close_side = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": float(close_vol),
            "type": close_side,
            "price": float(close_price),
            "deviation": 20,
            "magic": pos.magic,
            "comment": f"Close pos #{ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        res = mt5.order_send(request)
        if res is None:
            err = mt5.last_error()
            return CloseResult(success=False, ticket=ticket, closed_volume=0.0, close_price=0.0, realized_pnl=0.0, retcode=err[0], comment=err[1])

        return CloseResult(
            success=(res.retcode == mt5.TRADE_RETCODE_DONE),
            ticket=ticket,
            closed_volume=res.volume,
            close_price=res.price,
            realized_pnl=float(pos.profit),
            retcode=res.retcode,
            comment=res.comment,
        )

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve list of active open positions."""
        results = []
        if self.config.is_paper_mode or mt5_manager.is_mock_mode:
            raw_positions = mock_mt5_instance.positions_get(symbol=symbol)
            for p in raw_positions:
                results.append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == ORDER_TYPE_BUY else "SELL",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "price_current": p.price_current,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                    "time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
                    "comment": p.comment,
                    "magic": p.magic,
                })
            return results

        if not _MT5_AVAILABLE or mt5 is None:
            return []

        try:
            raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if raw:
                for p in raw:
                    results.append({
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                        "volume": p.volume,
                        "price_open": p.price_open,
                        "price_current": p.price_current,
                        "sl": p.sl,
                        "tp": p.tp,
                        "profit": p.profit,
                        "time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
                        "comment": p.comment,
                        "magic": p.magic,
                    })
        except Exception as e:
            logger.error("Error getting MT5 positions: %s", e)

        return results

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve active pending orders."""
        if self.config.is_paper_mode or mt5_manager.is_mock_mode:
            return mock_mt5_instance.orders_get(symbol=symbol)

        if not _MT5_AVAILABLE or mt5 is None:
            return []

        try:
            raw = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
            if raw:
                return [o._asdict() for o in raw]
        except Exception as e:
            logger.error("Error getting MT5 pending orders: %s", e)
        return []

    def get_trade_history(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve historical trades / deals."""
        if self.config.is_paper_mode or mt5_manager.is_mock_mode:
            return mock_mt5_instance.history_deals_get(date_from=from_date, date_to=to_date)

        if not _MT5_AVAILABLE or mt5 is None:
            return []

        try:
            start = from_date or datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = to_date or datetime.now(timezone.utc)
            deals = mt5.history_deals_get(start, end)
            if deals:
                return [d._asdict() for d in deals]
        except Exception as e:
            logger.error("Error reading MT5 trade history: %s", e)
        return []


# Global OrderService instance
order_service = OrderService()
