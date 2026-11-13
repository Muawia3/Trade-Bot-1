"""
SQLAlchemy ORM model for completed and active trades.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class Trade(Base, UUIDMixin, TimestampMixin):
    """
    Represents an executed trade (both live and paper).
    Stores execution parameters, pricing, profit/loss, and strategy tracking.
    """

    __tablename__ = "trades"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy' or 'sell'
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[float] = mapped_column(Float, nullable=False)  # Lot size
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", index=True
    )  # 'open', 'closed', 'cancelled', 'rejected'
    pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    swap: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    strategy_name: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    signal_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    is_paper: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_trades_symbol_status", "symbol", "status"),
        Index("idx_trades_strategy_opened", "strategy_name", "opened_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trade id={self.id} symbol={self.symbol} side={self.side} "
            f"volume={self.volume} pnl={self.pnl} status={self.status}>"
        )
