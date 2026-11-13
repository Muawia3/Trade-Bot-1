"""
Repository for BacktestResult operations.
"""

from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest_result import BacktestResult


class BacktestRepository:
    """Async repository for backtesting execution records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, result_model: BacktestResult) -> BacktestResult:
        """Save a new backtest result."""
        self.session.add(result_model)
        await self.session.flush()
        await self.session.refresh(result_model)
        return result_model

    async def get_by_id(self, result_id: str) -> Optional[BacktestResult]:
        """Fetch backtest result by ID."""
        stmt = select(BacktestResult).where(BacktestResult.id == result_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[BacktestResult]:
        """Query backtest results."""
        stmt = select(BacktestResult)
        if strategy_name:
            stmt = stmt.where(BacktestResult.strategy_name == strategy_name)
        if symbol:
            stmt = stmt.where(BacktestResult.symbol == symbol.upper())
        stmt = stmt.order_by(desc(BacktestResult.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, result_id: str) -> bool:
        """Delete backtest record."""
        res = await self.get_by_id(result_id)
        if not res:
            return False
        await self.session.delete(res)
        await self.session.flush()
        return True
