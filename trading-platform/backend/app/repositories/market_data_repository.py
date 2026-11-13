"""
Repository for Market Data: CandleData and TickData storage and queries.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import CandleData, TickData
from app.schemas.market_data import CandleDataCreate, TickDataCreate


class MarketDataRepository:
    """Async repository for time-series market candlestick and tick data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_candles(self, candles_in: List[CandleDataCreate]) -> int:
        """
        Bulk upsert candlestick records.
        Updates open/high/low/close/volume/spread if (symbol, timeframe, timestamp) conflicts.
        Returns the count of upserted candles.
        """
        if not candles_in:
            return 0

        dialect_name = self.session.bind.dialect.name if self.session.bind else "postgresql"
        data_dicts = [c.model_dump() for c in candles_in]

        # Ensure symbols and timeframes are standardized
        for d in data_dicts:
            d["symbol"] = d["symbol"].upper()
            d["timeframe"] = d["timeframe"].upper()

        if dialect_name == "postgresql":
            stmt = pg_insert(CandleData).values(data_dicts)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "timestamp"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "spread": stmt.excluded.spread,
                },
            )
            await self.session.execute(stmt)
        elif dialect_name == "sqlite":
            stmt = sqlite_insert(CandleData).values(data_dicts)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "timestamp"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "spread": stmt.excluded.spread,
                },
            )
            await self.session.execute(stmt)
        else:
            # Fallback iterative merge
            for c_dict in data_dicts:
                existing = await self.get_candle(
                    c_dict["symbol"], c_dict["timeframe"], c_dict["timestamp"]
                )
                if existing:
                    existing.open = c_dict["open"]
                    existing.high = c_dict["high"]
                    existing.low = c_dict["low"]
                    existing.close = c_dict["close"]
                    existing.volume = c_dict["volume"]
                    existing.spread = c_dict.get("spread", 0.0)
                else:
                    self.session.add(CandleData(**c_dict))

        await self.session.flush()
        return len(candles_in)

    async def get_candle(
        self, symbol: str, timeframe: str, timestamp: datetime
    ) -> Optional[CandleData]:
        """Fetch a single candle by unique key."""
        stmt = select(CandleData).where(
            and_(
                CandleData.symbol == symbol.upper(),
                CandleData.timeframe == timeframe.upper(),
                CandleData.timestamp == timestamp,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[CandleData]:
        """
        Query chronological candles for a symbol and timeframe.
        Returns ordered oldest to newest.
        """
        conditions = [
            CandleData.symbol == symbol.upper(),
            CandleData.timeframe == timeframe.upper(),
        ]
        if start_date:
            conditions.append(CandleData.timestamp >= start_date)
        if end_date:
            conditions.append(CandleData.timestamp <= end_date)

        # To get the latest N candles in chronological order, query descending and reverse
        stmt = (
            select(CandleData)
            .where(and_(*conditions))
            .order_by(desc(CandleData.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        candles = list(result.scalars().all())
        candles.reverse()
        return candles

    async def get_latest_candle(
        self, symbol: str, timeframe: str
    ) -> Optional[CandleData]:
        """Fetch the most recent candle."""
        stmt = (
            select(CandleData)
            .where(
                and_(
                    CandleData.symbol == symbol.upper(),
                    CandleData.timeframe == timeframe.upper(),
                )
            )
            .order_by(desc(CandleData.timestamp))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_tick(self, tick_in: TickDataCreate) -> TickData:
        """Record an incoming tick quote."""
        data = tick_in.model_dump()
        data["symbol"] = data["symbol"].upper()
        tick = TickData(**data)
        self.session.add(tick)
        await self.session.flush()
        await self.session.refresh(tick)
        return tick

    async def get_latest_tick(self, symbol: str) -> Optional[TickData]:
        """Fetch the latest recorded tick for a symbol."""
        stmt = (
            select(TickData)
            .where(TickData.symbol == symbol.upper())
            .order_by(desc(TickData.timestamp))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_ticks(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[TickData]:
        """Query tick history."""
        conditions = [TickData.symbol == symbol.upper()]
        if start_date:
            conditions.append(TickData.timestamp >= start_date)
        if end_date:
            conditions.append(TickData.timestamp <= end_date)

        stmt = (
            select(TickData)
            .where(and_(*conditions))
            .order_by(desc(TickData.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        ticks = list(result.scalars().all())
        ticks.reverse()
        return ticks
