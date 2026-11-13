"""
Risk Metrics module.
Calculates risk/reward ratio, mathematical expectancy, Kelly criterion,
position risk exposure, and portfolio heat.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from app.core.logging_config import get_logger

logger = get_logger("risk.metrics")


@dataclass
class RiskMetricsSummary:
    """Consolidated risk metrics representation."""
    risk_reward_ratio: float
    expected_value: float
    kelly_fraction: float
    half_kelly: float
    position_risk_percent: float
    portfolio_heat_percent: float


class RiskMetricsCalculator:
    """Calculates quantitative risk and money management metrics."""

    @staticmethod
    def calculate_risk_reward_ratio(entry_price: float, sl_price: float, tp_price: float) -> float:
        """
        Calculates Risk/Reward ratio: abs(tp - entry) / abs(entry - sl).
        """
        risk_dist = abs(entry_price - sl_price)
        if risk_dist <= 0:
            return 0.0
        reward_dist = abs(tp_price - entry_price)
        return round(reward_dist / risk_dist, 2)

    @staticmethod
    def calculate_expected_value(
        win_rate: float,
        avg_win_amount: float,
        avg_loss_amount: float,
    ) -> float:
        """
        Calculates Mathematical Expectancy per trade:
        EV = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        """
        win_prob = max(0.0, min(1.0, win_rate))
        loss_prob = 1.0 - win_prob
        ev = (win_prob * avg_win_amount) - (loss_prob * abs(avg_loss_amount))
        return round(ev, 2)

    @staticmethod
    def calculate_kelly_criterion(
        win_rate: float,
        avg_win_amount: float,
        avg_loss_amount: float,
    ) -> float:
        """
        Calculates Kelly Criterion optimal risk percentage:
        K% = W - [(1 - W) / R]
        where W = win probability, R = payoff ratio (avg_win / avg_loss).
        Returns capped Kelly fraction (0.0 to 0.25).
        """
        if avg_loss_amount <= 0 or win_rate <= 0:
            return 0.0

        win_prob = max(0.0, min(1.0, win_rate))
        payoff_ratio = avg_win_amount / abs(avg_loss_amount)

        if payoff_ratio <= 0:
            return 0.0

        kelly = win_prob - ((1.0 - win_prob) / payoff_ratio)
        # Cap to 0.0 minimum and 0.25 (25%) maximum safety buffer
        clamped_kelly = max(0.0, min(0.25, kelly))
        return round(clamped_kelly, 4)

    @staticmethod
    def calculate_position_risk_percent(
        volume_lots: float,
        stop_loss_distance: float,
        account_balance: float,
        symbol_info: Dict[str, Any],
    ) -> float:
        """
        Calculates monetary risk of a single position as a percentage of account balance.
        """
        if account_balance <= 0 or volume_lots <= 0:
            return 0.0

        contract_size = float(symbol_info.get("trade_contract_size", 100000.0))
        tick_value = float(symbol_info.get("trade_tick_value", 0.0))
        tick_size = float(symbol_info.get("trade_tick_size", symbol_info.get("point", 0.00001)))

        if tick_value > 0 and tick_size > 0:
            ticks = stop_loss_distance / tick_size
            loss_for_trade = ticks * tick_value * volume_lots
        else:
            loss_for_trade = stop_loss_distance * contract_size * volume_lots

        pct = (loss_for_trade / account_balance) * 100.0
        return round(pct, 2)

    @staticmethod
    def calculate_portfolio_heat(
        open_positions: List[Dict[str, Any]],
        account_equity: float,
    ) -> float:
        """
        Calculates total portfolio heat: sum of all open position risk amounts
        divided by current account equity.
        """
        if account_equity <= 0:
            return 0.0

        total_risk_dollars = 0.0
        for pos in open_positions:
            risk_dollars = pos.get("risk_amount")
            if risk_dollars is not None:
                total_risk_dollars += float(risk_dollars)
            else:
                # Estimate from volume, sl, open price if available
                vol = float(pos.get("volume", 0.0))
                open_p = float(pos.get("open_price", 0.0))
                sl_p = float(pos.get("stop_loss", 0.0))
                contract = float(pos.get("contract_size", 100000.0))
                if open_p > 0 and sl_p > 0:
                    dist = abs(open_p - sl_p)
                    total_risk_dollars += dist * contract * vol

        heat_pct = (total_risk_dollars / account_equity) * 100.0
        return round(heat_pct, 2)
