"""
Paper Account Manager.

Manages multiple paper trading accounts, account creation, deletion,
balance resets, trade history retrieval, and account-level performance metrics.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.paper_trading.paper_engine import PaperPosition, PaperTradingEngine

logger = get_logger("paper_trading.account_manager")


@dataclass
class PaperAccountInfo:
    """Metadata and statistics for a single paper trading account."""

    account_id: str
    name: str
    currency: str = "USD"
    initial_balance: float = 10000.0
    leverage: float = 100.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = "Paper Trading Account"
    is_active: bool = True


class PaperAccountManager:
    """
    Manages a collection of paper trading engines/accounts.
    Provides methods to create, switch, reset, and retrieve performance stats.
    """

    def __init__(self) -> None:
        self.accounts: Dict[str, PaperAccountInfo] = {}
        self.engines: Dict[str, PaperTradingEngine] = {}
        self.default_account_id: str = "default"

        # Initialize the default account
        settings = get_settings()
        self.create_account(
            name="Default Paper Account",
            initial_balance=settings.PAPER_TRADING_INITIAL_BALANCE,
            currency=settings.PAPER_TRADING_CURRENCY,
            account_id=self.default_account_id,
            description="System default simulated account",
        )

    def create_account(
        self,
        name: str,
        initial_balance: float = 10000.0,
        currency: str = "USD",
        leverage: float = 100.0,
        account_id: Optional[str] = None,
        description: str = "",
    ) -> PaperAccountInfo:
        """Create a new paper trading account and its dedicated engine."""
        acc_id = account_id or f"paper_{uuid.uuid4().hex[:8]}"

        if acc_id in self.accounts:
            logger.warning("Paper account '%s' already exists. Returning existing account.", acc_id)
            return self.accounts[acc_id]

        info = PaperAccountInfo(
            account_id=acc_id,
            name=name,
            currency=currency,
            initial_balance=initial_balance,
            leverage=leverage,
            description=description,
        )

        engine = PaperTradingEngine(
            initial_balance=initial_balance,
            currency=currency,
            leverage=leverage,
        )

        self.accounts[acc_id] = info
        self.engines[acc_id] = engine

        logger.info("Created paper account [%s] '%s' with $%.2f", acc_id, name, initial_balance)
        return info

    def get_account_engine(self, account_id: Optional[str] = None) -> PaperTradingEngine:
        """Get the PaperTradingEngine instance for a given account id (or default)."""
        target_id = account_id or self.default_account_id
        if target_id not in self.engines:
            logger.warning(
                "Account '%s' not found. Falling back to default account '%s'",
                target_id,
                self.default_account_id,
            )
            target_id = self.default_account_id

        return self.engines[target_id]

    def delete_account(self, account_id: str) -> bool:
        """Delete a paper account. Cannot delete default account."""
        if account_id == self.default_account_id:
            logger.warning("Attempted to delete the default paper account. Action denied.")
            return False

        if account_id in self.accounts:
            del self.accounts[account_id]
            del self.engines[account_id]
            logger.info("Deleted paper account [%s]", account_id)
            return True

        return False

    def reset_account(
        self,
        account_id: Optional[str] = None,
        new_balance: Optional[float] = None,
    ) -> bool:
        """Reset the balance and wipe trade history for an account."""
        acc_id = account_id or self.default_account_id
        if acc_id not in self.engines:
            return False

        info = self.accounts[acc_id]
        balance_to_set = new_balance if new_balance is not None else info.initial_balance
        self.engines[acc_id].reset(initial_balance=balance_to_set, currency=info.currency)
        logger.info("Reset paper account [%s] to $%.2f", acc_id, balance_to_set)
        return True

    def get_trade_history(
        self,
        account_id: Optional[str] = None,
        limit: int = 100,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve trade history for an account."""
        engine = self.get_account_engine(account_id)
        trades = engine.history

        if symbol:
            trades = [t for t in trades if t.symbol.upper() == symbol.upper()]

        # Return latest first
        sorted_trades = sorted(
            trades,
            key=lambda x: x.close_time or x.open_time,
            reverse=True,
        )
        return [t.to_dict() for t in sorted_trades[:limit]]

    def get_account_performance(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate performance metrics for a paper trading account.
        Calculates:
        - Total Net Profit, Return %
        - Win rate, Total trades, Wins, Losses, Break-even
        - Profit Factor, Gross Profit, Gross Loss
        - Average Win, Average Loss, Win/Loss Ratio
        - Max Drawdown ($ and %)
        """
        engine = self.get_account_engine(account_id)
        trades = engine.history
        summary = engine.get_account_summary()

        total_trades = len(trades)
        if total_trades == 0:
            return {
                "account_id": account_id or self.default_account_id,
                "balance": summary["balance"],
                "equity": summary["equity"],
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "break_even_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_profit": 0.0,
                "total_return_pct": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "max_drawdown_amount": 0.0,
                "max_drawdown_pct": 0.0,
            }

        pnls = [t.realized_pnl - t.commission + t.swap for t in trades]
        wins = [p for p in pnls if p > 0.001]
        losses = [p for p in pnls if p < -0.001]
        break_even = [p for p in pnls if abs(p) <= 0.001]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_profit = sum(pnls)

        win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (999.0 if gross_profit > 0 else 0.0)
        )

        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses)) / len(losses) if losses else 0.0

        # Equity curve & Max drawdown calculation
        initial = engine.initial_balance
        peak = initial
        running_equity = initial
        max_dd_amount = 0.0
        max_dd_pct = 0.0

        for pnl in pnls:
            running_equity += pnl
            if running_equity > peak:
                peak = running_equity
            dd_amount = peak - running_equity
            dd_pct = (dd_amount / peak) * 100.0 if peak > 0 else 0.0
            if dd_amount > max_dd_amount:
                max_dd_amount = dd_amount
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        total_return_pct = (
            (net_profit / engine.initial_balance) * 100.0
            if engine.initial_balance > 0
            else 0.0
        )

        return {
            "account_id": account_id or self.default_account_id,
            "balance": summary["balance"],
            "equity": summary["equity"],
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "break_even_trades": len(break_even),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_profit": round(net_profit, 2),
            "total_return_pct": round(total_return_pct, 2),
            "average_win": round(avg_win, 2),
            "average_loss": round(avg_loss, 2),
            "max_drawdown_amount": round(max_dd_amount, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
        }

    def list_accounts(self) -> List[Dict[str, Any]]:
        """List all managed paper trading accounts with their current summaries."""
        result = []
        for acc_id, info in self.accounts.items():
            engine = self.engines[acc_id]
            summary = engine.get_account_summary()
            result.append({
                "account_id": acc_id,
                "name": info.name,
                "description": info.description,
                "currency": info.currency,
                "leverage": info.leverage,
                "created_at": info.created_at.isoformat(),
                "balance": summary["balance"],
                "equity": summary["equity"],
                "open_positions": summary["open_positions_count"],
            })
        return result


# Singleton instance for application-wide use
_global_paper_account_manager: Optional[PaperAccountManager] = None


def get_paper_account_manager() -> PaperAccountManager:
    """Return the application singleton PaperAccountManager."""
    global _global_paper_account_manager
    if _global_paper_account_manager is None:
        _global_paper_account_manager = PaperAccountManager()
    return _global_paper_account_manager
