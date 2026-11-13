"""
SQLAlchemy ORM model for live/demo MT5 and platform account state.
"""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class Account(Base, UUIDMixin, TimestampMixin):
    """
    Represents an MT5 trading account or platform account profile.
    Maintains synchronization state with the broker server.
    """

    __tablename__ = "accounts"

    mt5_login: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True
    )
    broker: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    server: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="demo"
    )  # 'demo', 'real', 'paper'
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    equity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<Account id={self.id} login={self.mt5_login} broker={self.broker} "
            f"balance={self.balance} equity={self.equity}>"
        )
