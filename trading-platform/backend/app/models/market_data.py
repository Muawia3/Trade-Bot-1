"""
SQLAlchemy ORM models for OHLCV candlestick and tick market data.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDMixin


class CandleData(Base, UUIDMixin):
    """
    Stores historical and completed candlestick data.
    """

    __tablename__ = "candle_data"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spread: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle_symbol_tf_ts"),
        Index("idx_candles_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<CandleData symbol={self.symbol} tf={self.timeframe} "
            f"ts={self.timestamp} close={self.close}>"
        )


class TickData(Base, UUIDMixin):
    """
    Stores individual tick quotes received from data feeds.
    """

    __tablename__ = "tick_data"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    bid: Mapped[float] = mapped_column(Float, nullable=False)
    ask: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_ticks_symbol_ts", "symbol", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<TickData symbol={self.symbol} bid={self.bid} ask={self.ask} ts={self.timestamp}>"
        )
