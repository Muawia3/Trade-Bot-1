"""
Repository for Account database entity operations.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


class AccountRepository:
    """Async repository for MT5 and system accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, account_id: str) -> Optional[Account]:
        """Fetch account by ID."""
        stmt = select(Account).where(Account.id == account_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_login(self, mt5_login: int) -> Optional[Account]:
        """Fetch account by MT5 login number."""
        stmt = select(Account).where(Account.mt5_login == mt5_login)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_account(self) -> Optional[Account]:
        """Fetch primary active account."""
        stmt = select(Account).order_by(Account.created_at).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Account]:
        """Retrieve all registered accounts."""
        stmt = select(Account).order_by(Account.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_or_update(self, account_in: AccountCreate) -> Account:
        """Create a new account or update if login matches."""
        if account_in.mt5_login:
            existing = await self.get_by_login(account_in.mt5_login)
            if existing:
                for k, v in account_in.model_dump(exclude_unset=True).items():
                    setattr(existing, k, v)
                await self.session.flush()
                await self.session.refresh(existing)
                return existing

        account = Account(**account_in.model_dump())
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def update(self, account_id: str, account_in: AccountUpdate) -> Optional[Account]:
        """Update account balances or configuration."""
        account = await self.get_by_id(account_id)
        if not account:
            return None

        for k, v in account_in.model_dump(exclude_unset=True).items():
            setattr(account, k, v)

        await self.session.flush()
        await self.session.refresh(account)
        return account
