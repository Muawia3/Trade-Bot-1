"""
Stop Loss and Trailing Stop module.
Provides ATR-based, fixed pip, and percentage stop calculations with
strict broker minimum stop-level distance enforcement.
"""

from typing import Any, Dict, Optional, Tuple
from app.core.constants import OrderSide, SignalType
from app.core.logging_config import get_logger

logger = get_logger("risk.stop_loss")


class StopLossCalculator:
    """
    Computes and manages stop losses, take profits, and dynamic trailing stops.
    """

    @staticmethod
    def calculate_atr_stop(
        entry_price: float,
        side: OrderSide,
        atr_value: float,
        atr_multiplier: float = 1.5,
        digits: int = 5,
    ) -> float:
        """Calculates stop loss based on ATR volatility distance."""
        dist = atr_value * atr_multiplier
        if side == OrderSide.BUY:
            sl = entry_price - dist
        else:
            sl = entry_price + dist
        return round(float(sl), digits)

    @staticmethod
    def calculate_pip_stop(
        entry_price: float,
        side: OrderSide,
        pips: float,
        symbol_info: Dict[str, Any],
    ) -> float:
        """Calculates stop loss based on fixed pip distance."""
        digits = symbol_info.get("digits", 5)
        point = symbol_info.get("point", 10 ** -digits)
        pip_size = point * 10 if digits in (3, 5) else point
        dist = pips * pip_size

        if side == OrderSide.BUY:
            sl = entry_price - dist
        else:
            sl = entry_price + dist
        return round(float(sl), digits)

    @staticmethod
    def calculate_percentage_stop(
        entry_price: float,
        side: OrderSide,
        percent: float,
        digits: int = 5,
    ) -> float:
        """Calculates stop loss based on price percentage distance."""
        dist = entry_price * (percent / 100.0)
        if side == OrderSide.BUY:
            sl = entry_price - dist
        else:
            sl = entry_price + dist
        return round(float(sl), digits)

    @staticmethod
    def validate_broker_stop_distance(
        entry_price: float,
        sl_price: float,
        symbol_info: Dict[str, Any],
    ) -> Tuple[bool, float]:
        """
        Validates that the stop loss satisfies the broker's minimum stop level.

        Returns:
            Tuple of (is_valid, adjusted_or_original_sl_price).
        """
        digits = symbol_info.get("digits", 5)
        point = symbol_info.get("point", 10 ** -digits)
        stop_level_points = symbol_info.get("stops_level", symbol_info.get("stop_level", 0))
        min_dist = stop_level_points * point

        actual_dist = abs(entry_price - sl_price)
        if actual_dist < min_dist:
            logger.warning(
                "Stop loss distance %.5f is less than broker minimum required %.5f (stop_level=%d)",
                actual_dist,
                min_dist,
                stop_level_points,
            )
            # Adjust SL to minimum required distance
            if sl_price < entry_price:
                adjusted_sl = entry_price - min_dist
            else:
                adjusted_sl = entry_price + min_dist
            return False, round(adjusted_sl, digits)

        return True, sl_price

    @staticmethod
    def calculate_trailing_stop(
        current_price: float,
        side: OrderSide,
        open_price: float,
        current_sl: Optional[float],
        trailing_distance: float,
        trailing_step: float,
        digits: int = 5,
    ) -> Optional[float]:
        """
        Calculates updated trailing stop level when price moves in profit.

        Args:
            current_price: Current market bid/ask.
            side: OrderSide.BUY or OrderSide.SELL.
            open_price: Original fill price.
            current_sl: Current active stop loss price (or None).
            trailing_distance: Trailing gap distance in price units.
            trailing_step: Minimum favorable movement needed to step the stop loss.
            digits: Decimal precision.

        Returns:
            New stop loss price if an update is warranted, else None.
        """
        if side == OrderSide.BUY:
            # Trade must be in profit beyond trailing distance
            profit = current_price - open_price
            if profit < trailing_distance:
                return None

            proposed_sl = round(current_price - trailing_distance, digits)
            if current_sl is None:
                return proposed_sl

            # Only step if the improvement exceeds trailing_step
            if proposed_sl - current_sl >= trailing_step:
                return proposed_sl

        elif side == OrderSide.SELL:
            profit = open_price - current_price
            if profit < trailing_distance:
                return None

            proposed_sl = round(current_price + trailing_distance, digits)
            if current_sl is None:
                return proposed_sl

            if current_sl - proposed_sl >= trailing_step:
                return proposed_sl

        return None
