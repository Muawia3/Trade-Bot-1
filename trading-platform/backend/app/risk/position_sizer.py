"""
Position Sizer module.
Calculates broker-accurate lot sizes based on dynamic risk percentage,
real MT5 contract sizes, tick values, and volume steps.
NEVER assumes fixed pip values.
"""

import math
from typing import Any, Dict, Optional, Tuple

from app.core.constants import MAX_LOT_SIZE, MIN_LOT_SIZE
from app.core.logging_config import get_logger

logger = get_logger("risk.position_sizer")


class PositionSizer:
    """
    Computes precise order lot sizes adhering to broker specifications
    and user risk budgets.
    """

    def __init__(self, default_risk_percent: float = 1.0, max_lot_limit: float = 20.0):
        self.default_risk_percent = default_risk_percent
        self.max_lot_limit = min(max_lot_limit, MAX_LOT_SIZE)

    def calculate_lot_size(
        self,
        account_balance: float,
        risk_percent: float,
        stop_loss_distance: float,
        symbol_info: Dict[str, Any],
        entry_price: Optional[float] = None,
    ) -> float:
        """
        Calculates the executable lot size.

        Args:
            account_balance: Current account balance (or equity).
            risk_percent: Percentage of balance to risk (e.g. 1.0 = 1%).
            stop_loss_distance: Absolute difference between entry price and SL price in price points.
            symbol_info: Broker dictionary containing:
                - trade_contract_size (e.g. 100,000 for EURUSD, 100 for XAUUSD)
                - trade_tick_value (value of 1 tick for 1 lot in deposit currency)
                - trade_tick_size (size of 1 tick, e.g. 0.00001 or 0.01)
                - volume_min (e.g. 0.01)
                - volume_max (e.g. 100.0)
                - volume_step (e.g. 0.01)
                - digits (e.g. 5 or 2)
                - point (e.g. 0.00001)
            entry_price: Current market entry price (optional fallback).

        Returns:
            Calculated lot size clamped and stepped, or 0.0 if trade exceeds risk rules.
        """
        if account_balance <= 0:
            logger.warning("Account balance is zero or negative: %.2f", account_balance)
            return 0.0

        if stop_loss_distance <= 0:
            logger.warning("Invalid stop loss distance: %f", stop_loss_distance)
            return 0.0

        # 1. Total capital at risk in account deposit currency
        effective_risk_pct = min(risk_percent, 5.0)  # Absolute safety ceiling of 5%
        risk_amount = account_balance * (effective_risk_pct / 100.0)

        # 2. Extract broker specifications
        contract_size = float(symbol_info.get("trade_contract_size", 100000.0))
        tick_value = float(symbol_info.get("trade_tick_value", 0.0))
        tick_size = float(symbol_info.get("trade_tick_size", symbol_info.get("point", 0.00001)))
        vol_min = float(symbol_info.get("volume_min", MIN_LOT_SIZE))
        vol_max = min(float(symbol_info.get("volume_max", MAX_LOT_SIZE)), self.max_lot_limit)
        vol_step = float(symbol_info.get("volume_step", 0.01))

        # 3. Determine loss per 1.0 standard lot
        loss_per_lot = 0.0

        if tick_value > 0 and tick_size > 0:
            # Most precise MT5 broker formula:
            ticks = stop_loss_distance / tick_size
            loss_per_lot = ticks * tick_value
        else:
            # Fallback based on contract size and distance
            loss_per_lot = stop_loss_distance * contract_size

        if loss_per_lot <= 0:
            logger.warning("Loss per lot calculation yielded non-positive number: %f", loss_per_lot)
            return 0.0

        raw_lot = risk_amount / loss_per_lot

        # 4. Step alignment (floor to prevent exceeding risk amount)
        step_factor = 1.0 / vol_step
        stepped_lot = math.floor(raw_lot * step_factor) / step_factor

        # Round to appropriate precision according to volume_step
        decimals = max(0, -int(math.floor(math.log10(vol_step))))
        final_lot = round(stepped_lot, decimals)

        # 5. Boundary checks
        if final_lot < vol_min:
            logger.info(
                "Calculated lot (%f) is below broker minimum volume (%f) for risk $%.2f. Rejecting.",
                final_lot,
                vol_min,
                risk_amount,
            )
            return 0.0

        if final_lot > vol_max:
            logger.warning("Clamping lot size %f to maximum permitted %f", final_lot, vol_max)
            final_lot = vol_max

        logger.debug(
            "PositionSizer: Balance=$%.2f, Risk=%.1f%% ($%.2f), SL Distance=%.5f, "
            "Loss/Lot=$%.2f -> Final Lots=%.2f",
            account_balance,
            effective_risk_pct,
            risk_amount,
            stop_loss_distance,
            loss_per_lot,
            final_lot,
        )
        return final_lot
