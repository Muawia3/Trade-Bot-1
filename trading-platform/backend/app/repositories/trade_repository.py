"""
Repository for Trade database entity operations.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.schemas.trade import TradeCreate, TradeFilter, TradeStatistics, TradeUpdate


class TradeRepository:
    """Async database repository for trades."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, trade_in: TradeCreate) -> Trade:
        """Create and persist a new trade record."""
        trade_data = trade_in.model_dump(exclude_unset=True)
        if "opened_at" not in trade_data or trade_data["opened_at"] is None:
            trade_data["opened_at"] = datetime.now(timezone.utc)

        trade = Trade(**trade_data)
        self.session.add(trade)
        await self.session.flush()
        await self.session.refresh(trade)
        return trade

    async def get_by_id(self, trade_id: str) -> Optional[Trade]:
        """Retrieve a trade by primary key ID."""
        stmt = select(Trade).where(Trade.id == trade_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self, filters: Optional[TradeFilter] = None
    ) -> Tuple[List[Trade], int]:
        """
        Query trades with optional filters, pagination, and sorting.
        Returns a tuple of (trades_list, total_count).
        """
        conditions = []
        limit = 50
        offset = 0

        if filters:
            limit = filters.limit
            offset = filters.offset

            if filters.symbol:
                conditions.append(Trade.symbol == filters.symbol.upper())
            if filters.status:
                conditions.append(Trade.status == filters.status.lower())
            if filters.strategy_name:
                conditions.append(Trade.strategy_name == filters.strategy_name)
            if filters.is_paper is not None:
                conditions.append(Trade.is_paper == filters.is_paper)
            if filters.start_date:
                conditions.append(Trade.opened_at >= filters.start_date)
            if filters.end_date:
                conditions.append(Trade.opened_at <= filters.end_date)

        # Count total matching rows
        count_stmt = select(func.count(Trade.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Query paginated rows
        stmt = select(Trade)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(Trade.opened_at)).offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        trades = list(result.scalars().all())
        return trades, total_count

    async def get_open_trades(
        self, symbol: Optional[str] = None, is_paper: Optional[bool] = None
    ) -> List[Trade]:
        """Retrieve all currently active/open positions."""
        conditions = [Trade.status == "open"]
        if symbol:
            conditions.append(Trade.symbol == symbol.upper())
        if is_paper is not None:
            conditions.append(Trade.is_paper == is_paper)

        stmt = select(Trade).where(and_(*conditions)).order_by(desc(Trade.opened_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, trade_id: str, trade_in: TradeUpdate) -> Optional[Trade]:
        """Update fields of an existing trade."""
        trade = await self.get_by_id(trade_id)
        if not trade:
            return None

        update_data = trade_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(trade, key, value)

        await self.session.flush()
        await self.session.refresh(trade)
        return trade

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        commission: float = 0.0,
        swap: float = 0.0,
        notes: Optional[str] = None,
    ) -> Optional[Trade]:
        """Close an open trade with realized exit price and PnL."""
        trade = await self.get_by_id(trade_id)
        if not trade:
            return None

        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.commission = commission
        trade.swap = swap
        trade.status = "closed"
        trade.closed_at = datetime.now(timezone.utc)
        if notes:
            trade.notes = (trade.notes or "") + f" | {notes}"

        await self.session.flush()
        await self.session.refresh(trade)
        return trade

    async def delete(self, trade_id: str) -> bool:
        """Delete a trade record."""
        trade = await self.get_by_id(trade_id)
        if not trade:
            return False
        await self.session.delete(trade)
        await self.session.flush()
        return True

    async def get_statistics(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        is_paper: Optional[bool] = None,
    ) -> TradeStatistics:
        """Calculate aggregated trade performance metrics."""
        conditions = [Trade.status == "closed"]
        if symbol:
            conditions.append(Trade.symbol == symbol.upper())
        if strategy_name:
            conditions.append(Trade.strategy_name == strategy_name)
        if is_paper is not None:
            conditions.append(Trade.is_paper == is_paper)

        stmt = select(Trade).where(and_(*conditions))
        result = await self.session.execute(stmt)
        closed_trades = list(result.scalars().all())

        total = len(closed_trades)
        if total == 0:
            return TradeStatistics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                profit_factor=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                average_trade=0.0,
                max_drawdown=0.0,
            )

        winning = [t for t in closed_trades if t.pnl > 0]
        losing = [t for t in closed_trades if t.pnl < 0]
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        total_pnl = sum(t.pnl for t in closed_trades)

        profit_factor = (
            (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
        )
        win_rate = (len(winning) / total) * 100.0
        avg_trade = total_pnl / total

        # Calculate max drawdown from equity progression
        peak = 0.0
        current_eq = 0.0
        max_dd = 0.0
        for t in sorted(closed_trades, key=lambda x: x.closed_at or x.opened_at):
            current_eq += t.pnl
            if current_eq > peak:
                peak = current_eq
            dd = peak - current_eq
            if dd > max_dd:
                max_dd = dd

        return TradeStatistics(
            total_trades=total,
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            profit_factor=round(profit_factor, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            average_trade=round(avg_trade, 2),
            max_drawdown=round(max_dd, 2),
        )
