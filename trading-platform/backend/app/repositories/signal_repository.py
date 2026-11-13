"""
Repository for Signal database entity operations.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.schemas.signal import SignalCreate, SignalFilter, SignalUpdate


class SignalRepository:
    """Async database repository for trading signals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, signal_in: SignalCreate) -> Signal:
        """Persist a new signal."""
        data = signal_in.model_dump(exclude_unset=True)
        if "created_at" not in data or data["created_at"] is None:
            data["created_at"] = datetime.now(timezone.utc)

        signal = Signal(**data)
        self.session.add(signal)
        await self.session.flush()
        await self.session.refresh(signal)
        return signal

    async def get_by_id(self, signal_id: str) -> Optional[Signal]:
        """Retrieve a signal by ID."""
        stmt = select(Signal).where(Signal.id == signal_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self, filters: Optional[SignalFilter] = None
    ) -> Tuple[List[Signal], int]:
        """
        Query signals with optional filters and pagination.
        Returns (signals_list, total_count).
        """
        conditions = []
        limit = 50
        offset = 0
        now = datetime.now(timezone.utc)

        if filters:
            limit = filters.limit
            offset = filters.offset

            if filters.symbol:
                conditions.append(Signal.symbol == filters.symbol.upper())
            if filters.signal_type:
                conditions.append(Signal.signal_type == filters.signal_type.upper())
            if filters.strategy_name:
                conditions.append(Signal.strategy_name == filters.strategy_name)
            if filters.timeframe:
                conditions.append(Signal.timeframe == filters.timeframe.upper())
            if filters.acted_on is not None:
                conditions.append(Signal.acted_on == filters.acted_on)
            if filters.active_only:
                conditions.append(Signal.acted_on == False)  # noqa: E712
                conditions.append(
                    or_(Signal.expired_at.is_(None), Signal.expired_at > now)
                )

        count_stmt = select(func.count(Signal.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        stmt = select(Signal)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(Signal.created_at)).offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        signals = list(result.scalars().all())
        return signals, total_count

    async def get_active_signals(
        self, symbol: Optional[str] = None
    ) -> List[Signal]:
        """Retrieve all currently active, valid, non-expired, unacted signals."""
        now = datetime.now(timezone.utc)
        conditions = [
            Signal.acted_on == False,  # noqa: E712
            or_(Signal.expired_at.is_(None), Signal.expired_at > now),
        ]
        if symbol:
            conditions.append(Signal.symbol == symbol.upper())

        stmt = select(Signal).where(and_(*conditions)).order_by(desc(Signal.confidence))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, signal_id: str, signal_in: SignalUpdate) -> Optional[Signal]:
        """Update signal properties."""
        signal = await self.get_by_id(signal_id)
        if not signal:
            return None

        update_data = signal_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(signal, key, value)

        await self.session.flush()
        await self.session.refresh(signal)
        return signal

    async def mark_acted_on(self, signal_id: str) -> Optional[Signal]:
        """Mark a signal as executed/acted upon."""
        signal = await self.get_by_id(signal_id)
        if not signal:
            return None
        signal.acted_on = True
        await self.session.flush()
        await self.session.refresh(signal)
        return signal

    async def delete(self, signal_id: str) -> bool:
        """Remove a signal."""
        signal = await self.get_by_id(signal_id)
        if not signal:
            return False
        await self.session.delete(signal)
        await self.session.flush()
        return True
