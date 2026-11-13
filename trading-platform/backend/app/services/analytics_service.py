"""
Analytics Service.

Provides consolidated quantitative metrics, performance summaries,
equity curves, and strategy comparisons for API endpoints and dashboard UI components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging_config import get_logger
from app.paper_trading.paper_account_manager import get_paper_account_manager
from app.paper_trading.paper_engine import PaperTradingEngine
from app.portfolio.portfolio_analytics import PortfolioAnalytics
from app.portfolio.portfolio_manager import PortfolioManager

logger = get_logger("services.analytics_service")


class AnalyticsService:
    """
    Service layer providing performance analytics, risk analysis,
    and strategy benchmarking across the platform.
    """

    def __init__(
        self,
        paper_engine: Optional[PaperTradingEngine] = None,
        portfolio_manager: Optional[PortfolioManager] = None,
        portfolio_analytics: Optional[PortfolioAnalytics] = None,
    ) -> None:
        self.account_manager = get_paper_account_manager()
        self.paper_engine = paper_engine or self.account_manager.get_account_engine()
        self.portfolio_manager = portfolio_manager or PortfolioManager(paper_engine=self.paper_engine)
        self.portfolio_analytics = portfolio_analytics or PortfolioAnalytics(paper_engine=self.paper_engine)

        logger.info("AnalyticsService initialized.")

    # -------------------------------------------------------------------------
    # Performance Dashboard Data
    # -------------------------------------------------------------------------
    def get_dashboard_summary(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Produce a unified dashboard overview containing:
        - Account metrics (Balance, Equity, Margin, Free Margin)
        - Performance stats (Win Rate, Net Profit, Profit Factor, Max Drawdown)
        - Active open positions & exposure summary
        - Portfolio heat & correlation warnings
        - Recent trade history
        """
        engine = self.account_manager.get_account_engine(account_id)
        account_summary = engine.get_account_summary()
        performance = self.account_manager.get_account_performance(account_id)
        exposure = self.portfolio_manager.calculate_total_exposure()
        heat = self.portfolio_manager.calculate_portfolio_heat()
        corr_risk = self.portfolio_manager.check_correlation_risk("XAUUSD", "EURUSD")

        # Fetch recent 10 trades
        recent_trades = self.account_manager.get_trade_history(account_id=account_id, limit=10)

        # Open positions formatted
        open_positions = [p.to_dict() for p in engine.get_open_positions()]

        return {
            "account": account_summary,
            "performance": performance,
            "portfolio": {
                "exposure": exposure,
                "heat": heat,
                "correlation": corr_risk,
                "open_positions": open_positions,
            },
            "recent_trades": recent_trades,
        }

    # -------------------------------------------------------------------------
    # Equity Curve & Drawdown Series
    # -------------------------------------------------------------------------
    def get_equity_curve(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate time-series equity curve and running drawdown series from closed trades.
        """
        engine = self.account_manager.get_account_engine(account_id)
        trades = sorted(
            engine.history,
            key=lambda x: x.close_time or x.open_time,
        )

        initial = engine.initial_balance
        equity_points: List[Dict[str, Any]] = [
            {"time": "Initial", "equity": initial, "balance": initial, "drawdown_pct": 0.0}
        ]

        running_balance = initial
        running_peak = initial

        for t in trades:
            net_pnl = t.realized_pnl - t.commission + t.swap
            running_balance += net_pnl
            if running_balance > running_peak:
                running_peak = running_balance

            dd_amount = running_peak - running_balance
            dd_pct = (dd_amount / running_peak) * 100.0 if running_peak > 0 else 0.0
            ts_str = t.close_time.isoformat() if t.close_time else "N/A"

            equity_points.append({
                "time": ts_str,
                "equity": round(running_balance, 2),
                "balance": round(running_balance, 2),
                "drawdown_pct": round(dd_pct, 2),
            })

        return {
            "initial_balance": initial,
            "current_balance": round(running_balance, 2),
            "total_points": len(equity_points),
            "series": equity_points,
        }

    # -------------------------------------------------------------------------
    # Strategy Comparison Matrix
    # -------------------------------------------------------------------------
    def get_strategy_comparison(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Produce a comparison table across all strategies executed in the account.
        """
        engine = self.account_manager.get_account_engine(account_id)
        strategy_stats = self.portfolio_analytics.get_strategy_performance(trades=engine.history)
        rankings = self.portfolio_analytics.get_strategy_rankings(trades=engine.history)

        return {
            "strategies_evaluated": len(strategy_stats),
            "best_performer": rankings.get("best_strategy"),
            "worst_performer": rankings.get("worst_strategy"),
            "comparison_matrix": list(strategy_stats.values()),
        }

    # -------------------------------------------------------------------------
    # Instrument Performance Breakdown
    # -------------------------------------------------------------------------
    def get_instrument_breakdown(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Produce breakdown of win rate, net PnL, and trade count per instrument.
        """
        engine = self.account_manager.get_account_engine(account_id)
        instrument_stats = self.portfolio_analytics.get_instrument_performance(trades=engine.history)
        periodic_pnl = self.portfolio_analytics.get_periodic_pnl(trades=engine.history)
        var_data = self.portfolio_analytics.calculate_value_at_risk(trades=engine.history)

        return {
            "by_instrument": instrument_stats,
            "periodic_pnl": periodic_pnl,
            "value_at_risk": var_data,
        }


# Global Singleton Instance
_global_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Return the application singleton AnalyticsService."""
    global _global_analytics_service
    if _global_analytics_service is None:
        _global_analytics_service = AnalyticsService()
    return _global_analytics_service
