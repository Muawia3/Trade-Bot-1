"""
Portfolio Analytics.

Computes multi-dimensional performance analytics across instruments, strategies,
time intervals (daily, weekly, monthly), risk-adjusted metrics, and portfolio Value at Risk (VaR).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger
from app.paper_trading.paper_engine import PaperPosition, PaperTradingEngine

logger = get_logger("portfolio.analytics")


class PortfolioAnalytics:
    """
    Analyzes historical trade executions and returns granular breakdown metrics.
    """

    def __init__(self, paper_engine: Optional[PaperTradingEngine] = None) -> None:
        self.paper_engine = paper_engine or PaperTradingEngine()
        logger.info("PortfolioAnalytics initialized.")

    # -------------------------------------------------------------------------
    # Time-Period P/L Breakdowns
    # -------------------------------------------------------------------------
    def get_periodic_pnl(
        self,
        trades: Optional[List[PaperPosition]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate daily, weekly, and monthly realized P/L from closed trades.
        """
        trade_list = trades if trades is not None else self.paper_engine.history
        daily: Dict[str, float] = defaultdict(float)
        weekly: Dict[str, float] = defaultdict(float)
        monthly: Dict[str, float] = defaultdict(float)

        for t in trade_list:
            if not t.close_time:
                continue
            dt = t.close_time
            day_key = dt.strftime("%Y-%m-%d")
            # ISO calendar: Year-WXX
            year, week_num, _ = dt.isocalendar()
            week_key = f"{year}-W{week_num:02d}"
            month_key = dt.strftime("%Y-%m")

            net_pnl = t.realized_pnl - t.commission + t.swap
            daily[day_key] += net_pnl
            weekly[week_key] += net_pnl
            monthly[month_key] += net_pnl

        return {
            "daily": {k: round(v, 2) for k, v in sorted(daily.items())},
            "weekly": {k: round(v, 2) for k, v in sorted(weekly.items())},
            "monthly": {k: round(v, 2) for k, v in sorted(monthly.items())},
        }

    # -------------------------------------------------------------------------
    # Breakdown by Instrument
    # -------------------------------------------------------------------------
    def get_instrument_performance(
        self,
        trades: Optional[List[PaperPosition]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Break down performance metrics per trading instrument (XAUUSD, EURUSD, etc.).
        """
        trade_list = trades if trades is not None else self.paper_engine.history
        grouped: Dict[str, List[float]] = defaultdict(list)

        for t in trade_list:
            sym = t.symbol.upper()
            net_pnl = t.realized_pnl - t.commission + t.swap
            grouped[sym].append(net_pnl)

        metrics_by_symbol: Dict[str, Dict[str, Any]] = {}
        for sym, pnls in grouped.items():
            total = len(pnls)
            wins = [p for p in pnls if p > 0.001]
            losses = [p for p in pnls if p < -0.001]
            gross_win = sum(wins)
            gross_loss = abs(sum(losses))
            net_pnl = sum(pnls)

            win_rate = (len(wins) / total) * 100.0 if total > 0 else 0.0
            profit_factor = (
                gross_win / gross_loss
                if gross_loss > 0
                else (999.0 if gross_win > 0 else 0.0)
            )

            metrics_by_symbol[sym] = {
                "total_trades": total,
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(win_rate, 2),
                "net_profit": round(net_pnl, 2),
                "gross_profit": round(gross_win, 2),
                "gross_loss": round(gross_loss, 2),
                "profit_factor": round(profit_factor, 2),
                "average_trade": round(net_pnl / total, 2) if total > 0 else 0.0,
            }

        return metrics_by_symbol

    # -------------------------------------------------------------------------
    # Breakdown by Strategy
    # -------------------------------------------------------------------------
    def get_strategy_performance(
        self,
        trades: Optional[List[PaperPosition]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Break down performance metrics per strategy (extracted from comment or tags).
        """
        trade_list = trades if trades is not None else self.paper_engine.history
        grouped: Dict[str, List[float]] = defaultdict(list)

        for t in trade_list:
            # Strategies often store their identifier in comment, e.g. "EMA_Crossover"
            strat_name = t.comment.split()[0] if t.comment else "Default"
            net_pnl = t.realized_pnl - t.commission + t.swap
            grouped[strat_name].append(net_pnl)

        metrics_by_strategy: Dict[str, Dict[str, Any]] = {}
        for strat, pnls in grouped.items():
            total = len(pnls)
            wins = [p for p in pnls if p > 0.001]
            losses = [p for p in pnls if p < -0.001]
            gross_win = sum(wins)
            gross_loss = abs(sum(losses))
            net_pnl = sum(pnls)

            win_rate = (len(wins) / total) * 100.0 if total > 0 else 0.0
            profit_factor = (
                gross_win / gross_loss
                if gross_loss > 0
                else (999.0 if gross_win > 0 else 0.0)
            )

            metrics_by_strategy[strat] = {
                "strategy_name": strat,
                "total_trades": total,
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(win_rate, 2),
                "net_profit": round(net_pnl, 2),
                "profit_factor": round(profit_factor, 2),
                "average_trade": round(net_pnl / total, 2) if total > 0 else 0.0,
            }

        return metrics_by_strategy

    def get_strategy_rankings(
        self,
        trades: Optional[List[PaperPosition]] = None,
    ) -> Dict[str, Any]:
        """Rank strategies by Net Profit and Profit Factor to identify best and worst performers."""
        strat_metrics = self.get_strategy_performance(trades)
        if not strat_metrics:
            return {"best_strategy": None, "worst_strategy": None, "ranked_strategies": []}

        ranked = sorted(
            strat_metrics.values(),
            key=lambda x: (x["net_profit"], x["profit_factor"]),
            reverse=True,
        )

        return {
            "best_strategy": ranked[0]["strategy_name"] if ranked else None,
            "worst_strategy": ranked[-1]["strategy_name"] if ranked else None,
            "ranked_strategies": ranked,
        }

    # -------------------------------------------------------------------------
    # Value at Risk (VaR)
    # -------------------------------------------------------------------------
    def calculate_value_at_risk(
        self,
        confidence_level: float = 0.95,
        trades: Optional[List[PaperPosition]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate Parametric and Historical 1-day Value at Risk (VaR)
        based on past trade PnL distributions.
        """
        trade_list = trades if trades is not None else self.paper_engine.history
        pnls = [t.realized_pnl - t.commission + t.swap for t in trade_list]

        summary = self.paper_engine.get_account_summary()
        equity = summary["equity"]

        if len(pnls) < 10 or equity <= 0:
            return {
                "confidence_level": confidence_level,
                "parametric_var_usd": 0.0,
                "historical_var_usd": 0.0,
                "var_pct_of_equity": 0.0,
                "sample_size": len(pnls),
            }

        pnl_arr = np.array(pnls)
        # Z-score for confidence level
        z_score = 1.645 if confidence_level == 0.95 else (2.326 if confidence_level == 0.99 else 1.96)

        mean_pnl = float(np.mean(pnl_arr))
        std_pnl = float(np.std(pnl_arr))

        # Parametric VaR: - (mean - z * std)
        param_var = max(0.0, -(mean_pnl - (z_score * std_pnl)))

        # Historical VaR: percentile of empirical distribution
        percentile_idx = (1.0 - confidence_level) * 100.0
        hist_pnl = float(np.percentile(pnl_arr, percentile_idx))
        hist_var = max(0.0, -hist_pnl)

        var_pct = (param_var / equity) * 100.0 if equity > 0 else 0.0

        return {
            "confidence_level": confidence_level,
            "parametric_var_usd": round(param_var, 2),
            "historical_var_usd": round(hist_var, 2),
            "var_pct_of_equity": round(var_pct, 2),
            "sample_size": len(pnls),
        }

    # -------------------------------------------------------------------------
    # Consolidated Performance Dashboard Data
    # -------------------------------------------------------------------------
    def get_dashboard_analytics(self) -> Dict[str, Any]:
        """Provide comprehensive analytics data package for frontend dashboards."""
        account_summary = self.paper_engine.get_account_summary()
        periodic = self.get_periodic_pnl()
        by_symbol = self.get_instrument_performance()
        by_strategy = self.get_strategy_performance()
        rankings = self.get_strategy_rankings()
        var_data = self.calculate_value_at_risk()

        return {
            "account_summary": account_summary,
            "periodic_pnl": periodic,
            "by_instrument": by_symbol,
            "by_strategy": by_strategy,
            "rankings": rankings,
            "risk_metrics": {
                "value_at_risk": var_data,
            },
        }
