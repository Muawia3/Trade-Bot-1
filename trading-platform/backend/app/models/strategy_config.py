"""
SQLAlchemy ORM model for automated strategy configurations.
"""

from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class StrategyConfig(Base, UUIDMixin, TimestampMixin):
    """
    Persisted configuration, runtime flags, and parameter sets for trading strategies.
    """

    __tablename__ = "strategy_configs"

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="M15")
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    risk_percent: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    def __repr__(self) -> str:
        return (
            f"<StrategyConfig name={self.name} symbol={self.symbol} "
            f"enabled={self.enabled} tf={self.timeframe}>"
        )
