"""
Account management and broker synchronization endpoints.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.connection import get_db
from app.repositories.account_repository import AccountRepository
from app.schemas.account import (
    AccountCreate,
    AccountOverview,
    AccountResponse,
    AccountUpdate,
)

router = APIRouter(prefix="/account", tags=["account"])


@router.get("", response_model=AccountResponse)
async def get_active_account(
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """
    Retrieve the primary active trading account.
    """
    repo = AccountRepository(db)
    account = await repo.get_default_account()
    if not account:
        # If no account exists yet, initialize a default one matching settings
        settings = get_settings()
        created = await repo.create_or_update(
            AccountCreate(
                mt5_login=settings.MT5_LOGIN,
                broker="MetaQuotes",
                server=settings.MT5_SERVER or "MetaQuotes-Demo",
                account_type="paper" if settings.is_paper_trading else "demo",
                currency="USD",
                leverage=100,
                balance=settings.PAPER_TRADING_INITIAL_BALANCE,
                equity=settings.PAPER_TRADING_INITIAL_BALANCE,
                is_demo=not settings.is_live_trading,
            )
        )
        return AccountResponse.model_validate(created)

    return AccountResponse.model_validate(account)


@router.get("/all", response_model=List[AccountResponse])
async def list_all_accounts(
    db: AsyncSession = Depends(get_db),
) -> List[AccountResponse]:
    """List all registered MT5 / platform accounts."""
    repo = AccountRepository(db)
    accounts = await repo.get_all()
    return [AccountResponse.model_validate(a) for a in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def register_account(
    account_in: AccountCreate,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """Register or link a trading account."""
    repo = AccountRepository(db)
    account = await repo.create_or_update(account_in)
    return AccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    account_in: AccountUpdate,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """Update account attributes."""
    repo = AccountRepository(db)
    account = await repo.update(account_id, account_in)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id '{account_id}' not found.",
        )
    return AccountResponse.model_validate(account)


@router.get("/overview", response_model=AccountOverview)
async def get_account_overview(
    db: AsyncSession = Depends(get_db),
) -> AccountOverview:
    """
    Get full account overview with margin, equity, and connection state.
    """
    settings = get_settings()
    repo = AccountRepository(db)
    account = await repo.get_default_account()

    balance = account.balance if account else settings.PAPER_TRADING_INITIAL_BALANCE
    equity = account.equity if account else balance
    currency = account.currency if account else "USD"
    acc_id = account.id if account else "default"
    acc_type = account.account_type if account else ("paper" if settings.is_paper_trading else "demo")

    return AccountOverview(
        account_id=acc_id,
        account_type=acc_type,
        currency=currency,
        balance=balance,
        equity=equity,
        margin=0.0,
        free_margin=equity,
        margin_level=100.0,
        unrealized_pnl=round(equity - balance, 2),
        realized_daily_pnl=0.0,
        open_positions_count=0,
        is_connected=settings.mt5_configured or settings.is_paper_trading,
    )
