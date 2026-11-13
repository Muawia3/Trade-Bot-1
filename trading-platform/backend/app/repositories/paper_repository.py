"""
Repository for simulated paper trading: PaperAccount, PaperPosition, and PaperOrder.
"""

from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.paper_account import PaperAccount, PaperOrder, PaperPosition
from app.schemas.paper_trading import PaperAccountCreate, PaperOrderCreate


class PaperRepository:
    """Async repository for paper trading accounts, open positions, and orders."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_default_account(
        self, initial_balance: float = 10000.0, currency: str = "USD"
    ) -> PaperAccount:
        """Fetch or initialize the default paper trading account."""
        stmt = (
            select(PaperAccount)
            .options(
                selectinload(PaperAccount.positions),
                selectinload(PaperAccount.orders),
            )
            .order_by(PaperAccount.created_at)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            account = PaperAccount(
                name="Default Paper Account",
                initial_balance=initial_balance,
                current_balance=initial_balance,
                equity=initial_balance,
                currency=currency,
            )
            self.session.add(account)
            await self.session.flush()
            await self.session.refresh(account)
        return account

    async def get_account_by_id(self, account_id: str) -> Optional[PaperAccount]:
        """Fetch paper account with related positions and orders."""
        stmt = (
            select(PaperAccount)
            .options(
                selectinload(PaperAccount.positions),
                selectinload(PaperAccount.orders),
            )
            .where(PaperAccount.id == account_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def reset_account(
        self, account_id: str, new_balance: float = 10000.0
    ) -> Optional[PaperAccount]:
        """Reset paper balance to initial and delete all positions/orders."""
        account = await self.get_account_by_id(account_id)
        if not account:
            return None

        account.current_balance = new_balance
        account.equity = new_balance
        account.initial_balance = new_balance

        # Clear existing positions and orders
        account.positions.clear()
        account.orders.clear()

        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def get_position_by_id(self, position_id: str) -> Optional[PaperPosition]:
        """Fetch a single position by primary ID."""
        stmt = select(PaperPosition).where(PaperPosition.id == position_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_positions(
        self, account_id: str, symbol: Optional[str] = None
    ) -> List[PaperPosition]:
        """Retrieve all open positions for an account."""
        conditions = [PaperPosition.account_id == account_id]
        if symbol:
            conditions.append(PaperPosition.symbol == symbol.upper())
        stmt = select(PaperPosition).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_position(
        self,
        account_id: str,
        symbol: str,
        side: str,
        volume: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> PaperPosition:
        """Open a new paper position."""
        position = PaperPosition(
            account_id=account_id,
            symbol=symbol.upper(),
            side=side.lower(),
            volume=volume,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            pnl=0.0,
        )
        self.session.add(position)
        await self.session.flush()
        await self.session.refresh(position)
        return position

    async def close_position(
        self, position_id: str, exit_price: Optional[float] = None
    ) -> Optional[float]:
        """
        Close a paper position and update account balance.
        If exit_price is omitted, falls back dynamically to position's current_price or entry_price.
        Returns the realized PnL.
        """
        stmt = select(PaperPosition).where(PaperPosition.id == position_id)
        result = await self.session.execute(stmt)
        position = result.scalar_one_or_none()
        if not position:
            return None

        actual_exit_price = (
            exit_price
            if exit_price is not None and exit_price > 0
            else (position.current_price or position.entry_price)
        )

        # Calculate realized PnL based on position direction
        direction = 1.0 if position.side == "buy" else -1.0
        price_diff = (actual_exit_price - position.entry_price) * direction
        # Simple contract size normalization (100 for gold, 100000 for standard forex lot)
        multiplier = 100.0 if "XAU" in position.symbol else 100000.0
        realized_pnl = price_diff * position.volume * multiplier

        # Update account balance
        account = await self.get_account_by_id(position.account_id)
        if account:
            account.current_balance += realized_pnl
            account.equity += realized_pnl

        await self.session.delete(position)
        await self.session.flush()
        return realized_pnl

    async def add_order(
        self, account_id: str, order_in: PaperOrderCreate
    ) -> PaperOrder:
        """Create a pending or filled paper order."""
        order = PaperOrder(
            account_id=account_id,
            symbol=order_in.symbol.upper(),
            side=order_in.side.lower(),
            volume=order_in.volume,
            order_type=order_in.order_type.lower(),
            price=order_in.price,
            status="pending",
        )
        self.session.add(order)
        await self.session.flush()
        await self.session.refresh(order)
        return order

    async def get_orders(
        self, account_id: str, status: Optional[str] = None
    ) -> List[PaperOrder]:
        """Fetch orders for an account."""
        conditions = [PaperOrder.account_id == account_id]
        if status:
            conditions.append(PaperOrder.status == status.lower())
        stmt = select(PaperOrder).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open paper order."""
        stmt = select(PaperOrder).where(PaperOrder.id == order_id)
        result = await self.session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            return False
        order.status = "cancelled"
        await self.session.flush()
        return True
