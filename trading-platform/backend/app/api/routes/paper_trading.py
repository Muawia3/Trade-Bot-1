"""
Simulated paper trading endpoints.
Provides complete account, order, and position tracking without broker or financial risk.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.connection import get_db
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper_trading import (
    PaperAccountReset,
    PaperAccountResponse,
    PaperOrderCreate,
    PaperOrderResponse,
    PaperPositionCloseRequest,
    PaperPositionResponse,
    PaperTradingStatus,
)
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.get("/status", response_model=PaperTradingStatus)
async def get_paper_trading_status(
    db: AsyncSession = Depends(get_db),
) -> PaperTradingStatus:
    """Retrieve full paper trading state including open positions and pending orders."""
    settings = get_settings()
    repo = PaperRepository(db)
    account = await repo.get_or_create_default_account(
        initial_balance=settings.PAPER_TRADING_INITIAL_BALANCE,
        currency=settings.PAPER_TRADING_CURRENCY,
    )

    positions = await repo.get_open_positions(account.id)
    orders = await repo.get_orders(account.id, status="pending")

    unrealized = sum(p.pnl for p in positions)

    return PaperTradingStatus(
        account=PaperAccountResponse.model_validate(account),
        open_positions=[PaperPositionResponse.model_validate(p) for p in positions],
        pending_orders=[PaperOrderResponse.model_validate(o) for o in orders],
        unrealized_pnl=round(unrealized, 2),
        margin_used=round(len(positions) * 100.0, 2),
        free_margin=round(account.equity - (len(positions) * 100.0), 2),
    )


@router.post("/reset", response_model=PaperAccountResponse)
async def reset_paper_account(
    payload: PaperAccountReset,
    db: AsyncSession = Depends(get_db),
) -> PaperAccountResponse:
    """Reset simulated paper balance and close all open positions."""
    repo = PaperRepository(db)
    account = await repo.get_or_create_default_account()
    reset_acc = await repo.reset_account(account.id, new_balance=payload.initial_balance)
    if not reset_acc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset paper account.",
        )

    await ws_manager.broadcast_account_update(
        {
            "action": "reset",
            "account_id": reset_acc.id,
            "balance": reset_acc.current_balance,
            "equity": reset_acc.equity,
        }
    )

    return PaperAccountResponse.model_validate(reset_acc)


@router.get("/positions", response_model=List[PaperPositionResponse])
async def get_paper_positions(
    db: AsyncSession = Depends(get_db),
) -> List[PaperPositionResponse]:
    """List all currently active paper positions."""
    repo = PaperRepository(db)
    account = await repo.get_or_create_default_account()
    positions = await repo.get_open_positions(account.id)
    return [PaperPositionResponse.model_validate(p) for p in positions]


@router.post("/orders", response_model=PaperOrderResponse, status_code=status.HTTP_201_CREATED)
async def place_paper_order(
    order_in: PaperOrderCreate,
    db: AsyncSession = Depends(get_db),
) -> PaperOrderResponse:
    """
    Submit a paper trading order.
    Market orders immediately instantiate an open PaperPosition.
    NEVER sends orders to MT5 terminal or external brokers.
    """
    repo = PaperRepository(db)
    account = await repo.get_or_create_default_account()

    order = await repo.add_order(account.id, order_in)

    # For market orders, immediately convert to an open position
    if order_in.order_type.lower() == "market":
        pos = await repo.add_position(
            account_id=account.id,
            symbol=order_in.symbol,
            side=order_in.side,
            volume=order_in.volume,
            entry_price=order_in.price,
            stop_loss=order_in.stop_loss,
            take_profit=order_in.take_profit,
        )
        order.status = "filled"

        await ws_manager.broadcast_trade_update(
            {
                "action": "paper_position_opened",
                "position": PaperPositionResponse.model_validate(pos).model_dump(mode="json"),
            }
        )

    return PaperOrderResponse.model_validate(order)


@router.post("/positions/{position_id}/close", response_model=dict)
async def close_paper_position(
    position_id: str,
    payload: PaperPositionCloseRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Close an open paper position and settle realized profit/loss."""
    repo = PaperRepository(db)

    # Determine dynamic exit price if none provided
    exit_price = payload.exit_price
    if exit_price is None or exit_price <= 0:
        pos = await repo.get_position_by_id(position_id)
        if not pos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paper position '{position_id}' not found.",
            )
        # Fetch latest market quote if available
        market_repo = MarketDataRepository(db)
        latest_tick = await market_repo.get_latest_tick(pos.symbol)
        if latest_tick:
            exit_price = latest_tick.bid if pos.side == "buy" else latest_tick.ask
        else:
            exit_price = pos.current_price or pos.entry_price

    realized_pnl = await repo.close_position(position_id, exit_price=exit_price)
    if realized_pnl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper position '{position_id}' not found.",
        )

    await ws_manager.broadcast_trade_update(
        {
            "action": "paper_position_closed",
            "position_id": position_id,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
        }
    )

    return {
        "status": "success",
        "position_id": position_id,
        "exit_price": round(exit_price, 5),
        "realized_pnl": round(realized_pnl, 2),
    }


@router.post("/orders/{order_id}/cancel", response_model=dict)
async def cancel_paper_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a pending paper order."""
    repo = PaperRepository(db)
    success = await repo.cancel_order(order_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper order '{order_id}' not found.",
        )
    return {"status": "success", "order_id": order_id}
