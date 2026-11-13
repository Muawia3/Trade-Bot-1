"""
Backtesting Performance Metrics.

Calculates comprehensive trading analytics, risk-adjusted returns,
drawdowns, and statistical metrics from trade histories and equity curves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger

logger = get_logger("backtesting.performance_metrics")


@dataclass
class TradeRecord:
    """Standardized representation of a single executed trade for metrics calculation."""

    trade_id: str
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    volume: float
    net_pnl: float
    gross_pnl: float
    commission: float = 0.0
    swap: float = 0.0
    return_pct: float = 0.0
    exit_reason: str = "close"


@dataclass
class PerformanceMetricsResult:
    """Comprehensive performance report data container."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    win_rate: float = 0.0

    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    total_return_pct: float = 0.0
    profit_factor: float = 0.0

    max_drawdown_amount: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_bars: int = 0

    average_win: float = 0.0
    average_loss: float = 0.0
    win_loss_ratio: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    expected_payoff: float = 0.0

    consecutive_wins_max: int = 0
    consecutive_losses_max: int = 0

    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    recovery_factor: float = 0.0

    total_commissions: float = 0.0
    average_trade_duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "break_even_trades": self.break_even_trades,
            "win_rate": round(self.win_rate, 2),
            "net_profit": round(self.net_profit, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown_amount": round(self.max_drawdown_amount, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "max_drawdown_duration_bars": self.max_drawdown_duration_bars,
            "average_win": round(self.average_win, 2),
            "average_loss": round(self.average_loss, 2),
            "win_loss_ratio": round(self.win_loss_ratio, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "expected_payoff": round(self.expected_payoff, 2),
            "consecutive_wins_max": self.consecutive_wins_max,
            "consecutive_losses_max": self.consecutive_losses_max,
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "recovery_factor": round(self.recovery_factor, 2),
            "total_commissions": round(self.total_commissions, 2),
            "average_trade_duration_seconds": round(self.average_trade_duration_seconds, 1),
        }


class PerformanceMetricsCalculator:
    """
    Computes professional quantitative metrics from trades and time-series equity curves.
    """

    @classmethod
    def calculate(
        cls,
        trades: Sequence[TradeRecord],
        equity_curve: Sequence[float],
        initial_balance: float = 10000.0,
        risk_free_rate: float = 0.02,
        annualization_factor: float = 252.0,
    ) -> PerformanceMetricsResult:
        """
        Calculate full metrics suite.

        :param trades: List of closed trade records.
        :param equity_curve: Array of equity values over time.
        :param initial_balance: Starting account capital.
        :param risk_free_rate: Annualized risk-free benchmark rate (e.g., 0.02 = 2%).
        :param annualization_factor: Trading days per year (252 default).
        """
        result = PerformanceMetricsResult()
        total_trades = len(trades)
        result.total_trades = total_trades

        if total_trades == 0 or len(equity_curve) == 0:
            return result

        # Extract PnL series
        pnls = [t.net_pnl for t in trades]
        commissions = [t.commission for t in trades]
        result.total_commissions = sum(commissions)

        wins = [p for p in pnls if p > 0.001]
        losses = [p for p in pnls if p < -0.001]
        break_evens = [p for p in pnls if abs(p) <= 0.001]

        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.break_even_trades = len(break_evens)
        result.win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_profit = sum(pnls)

        result.gross_profit = gross_profit
        result.gross_loss = gross_loss
        result.net_profit = net_profit
        result.total_return_pct = (
            (net_profit / initial_balance) * 100.0 if initial_balance > 0 else 0.0
        )

        result.profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (999.0 if gross_profit > 0 else 0.0)
        )

        result.average_win = (gross_profit / len(wins)) if wins else 0.0
        result.average_loss = (gross_loss / len(losses)) if losses else 0.0
        result.win_loss_ratio = (
            result.average_win / result.average_loss if result.average_loss > 0 else 0.0
        )
        result.largest_win = max(pnls) if pnls else 0.0
        result.largest_loss = min(pnls) if pnls else 0.0
        result.expected_payoff = net_profit / total_trades if total_trades > 0 else 0.0

        # Consecutive streaks
        curr_streak = 0
        max_wins = 0
        max_losses = 0

        for p in pnls:
            if p > 0:
                curr_streak = curr_streak + 1 if curr_streak > 0 else 1
                if curr_streak > max_wins:
                    max_wins = curr_streak
            elif p < 0:
                curr_streak = curr_streak - 1 if curr_streak < 0 else -1
                if abs(curr_streak) > max_losses:
                    max_losses = abs(curr_streak)
            else:
                curr_streak = 0

        result.consecutive_wins_max = max_wins
        result.consecutive_losses_max = max_losses

        # Trade duration calculation
        durations = [
            (t.exit_time - t.entry_time).total_seconds()
            for t in trades
            if t.exit_time and t.entry_time
        ]
        result.average_trade_duration_seconds = (
            sum(durations) / len(durations) if durations else 0.0
        )

        # Drawdown analysis from equity curve
        eq_arr = np.array(equity_curve, dtype=float)
        peaks = np.maximum.accumulate(eq_arr)
        drawdowns = peaks - eq_arr
        drawdown_pcts = np.where(peaks > 0, (drawdowns / peaks) * 100.0, 0.0)

        result.max_drawdown_amount = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        result.max_drawdown_pct = float(np.max(drawdown_pcts)) if len(drawdown_pcts) > 0 else 0.0

        # Drawdown duration calculation (bars in drawdown)
        max_dd_duration = 0
        curr_dd_duration = 0
        for dd in drawdowns:
            if dd > 0.001:
                curr_dd_duration += 1
                if curr_dd_duration > max_dd_duration:
                    max_dd_duration = curr_dd_duration
            else:
                curr_dd_duration = 0
        result.max_drawdown_duration_bars = max_dd_duration

        # Recovery Factor: Net Profit / Max Drawdown Amount
        result.recovery_factor = (
            (net_profit / result.max_drawdown_amount)
            if result.max_drawdown_amount > 0
            else 0.0
        )

        # Calmar Ratio: Annualized Return / Max Drawdown %
        # Assume period based on equity curve steps or trades
        calmar = (
            (result.total_return_pct / result.max_drawdown_pct)
            if result.max_drawdown_pct > 0
            else 0.0
        )
        result.calmar_ratio = calmar

        # Sharpe and Sortino ratios from percentage returns of equity curve
        if len(eq_arr) > 1:
            # Returns between points
            returns = np.diff(eq_arr) / eq_arr[:-1]
            returns = returns[~np.isnan(returns)]

            if len(returns) > 1 and np.std(returns) > 0:
                mean_ret = float(np.mean(returns))
                std_ret = float(np.std(returns))

                # Period risk free rate
                rf_per_period = (1.0 + risk_free_rate) ** (1.0 / annualization_factor) - 1.0
                excess_returns = returns - rf_per_period

                # Sharpe
                sharpe = (float(np.mean(excess_returns)) / std_ret) * math.sqrt(annualization_factor)
                result.sharpe_ratio = float(sharpe)

                # Sortino (downside deviation)
                negative_returns = returns[returns < 0]
                if len(negative_returns) > 0 and np.std(negative_returns) > 0:
                    downside_std = float(np.std(negative_returns))
                    sortino = (
                        float(np.mean(excess_returns)) / downside_std
                    ) * math.sqrt(annualization_factor)
                    result.sortino_ratio = float(sortino)
                else:
                    result.sortino_ratio = float(sharpe)

        return result
