"""
SQLAlchemy ORM models for simulated paper trading: accounts, positions, and orders.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin


class PaperAccount(Base, UUIDMixin):
    """
    Simulated broker account for paper trading without capital risk.
    """

    __tablename__ = "paper_accounts"

    name: Mapped[str] = mapped_column(String(50), nullable=False, default="Default Paper Account")
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    current_balance: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    equity: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    positions: Mapped[List["PaperPosition"]] = relationship(
        "PaperPosition", back_populates="account", cascade="all, delete-orphan"
    )
    orders: Mapped[List["PaperOrder"]] = relationship(
        "PaperOrder", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<PaperAccount id={self.id} name={self.name} "
            f"balance={self.current_balance} equity={self.equity}>"
        )


class PaperPosition(Base, UUIDMixin):
    """
    Open simulated position tracking floating PnL and risk thresholds.
    """

    __tablename__ = "paper_positions"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy' or 'sell'
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    account: Mapped["PaperAccount"] = relationship("PaperAccount", back_populates="positions")

    __table_args__ = (
        Index("idx_paper_pos_account_symbol", "account_id", "symbol"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperPosition id={self.id} symbol={self.symbol} side={self.side} "
            f"vol={self.volume} pnl={self.pnl}>"
        )


class PaperOrder(Base, UUIDMixin):
    """
    Pending or filled simulated order for paper trading.
    """

    __tablename__ = "paper_orders"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy' or 'sell'
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="market"
    )  # 'market', 'limit', 'stop'
    price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )  # 'pending', 'filled', 'cancelled', 'rejected'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    account: Mapped["PaperAccount"] = relationship("PaperAccount", back_populates="orders")

    __table_args__ = (
        Index("idx_paper_orders_account_status", "account_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperOrder id={self.id} symbol={self.symbol} type={self.order_type} "
            f"status={self.status}>"
        )
