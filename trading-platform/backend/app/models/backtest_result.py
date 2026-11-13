"""
SQLAlchemy ORM model for backtesting execution runs and analytics.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDMixin


class BacktestResult(Base, UUIDMixin):
    """
    Stores full metrics, executed trade log, and equity curve for historical backtests.
    """

    __tablename__ = "backtest_results"

    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="M15")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    final_balance: Mapped[float] = mapped_column(Float, nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Percentage, e.g. 55.5
    profit_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Percentage, e.g. 12.4
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    trades_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    equity_curve_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("idx_backtest_strategy_symbol", "strategy_name", "symbol"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestResult id={self.id} strategy={self.strategy_name} "
            f"symbol={self.symbol} win_rate={self.win_rate}% PF={self.profit_factor}>"
        )
