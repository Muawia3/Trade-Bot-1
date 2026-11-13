"""
Trade execution tracking, history, and position analytics API endpoints.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.repositories.trade_repository import TradeRepository
from app.schemas.trade import (
    TradeCreate,
    TradeFilter,
    TradeResponse,
    TradeStatistics,
    TradeUpdate,
)
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=Dict[str, Any])
async def list_trades(
    symbol: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    strategy_name: Optional[str] = Query(None),
    is_paper: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve paginated trade history with filters."""
    repo = TradeRepository(db)
    filters = TradeFilter(
        symbol=symbol,
        status=status_filter,
        strategy_name=strategy_name,
        is_paper=is_paper,
        limit=limit,
        offset=offset,
    )
    trades, total_count = await repo.get_multi(filters)
    return {
        "items": [TradeResponse.model_validate(t) for t in trades],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/open", response_model=List[TradeResponse])
async def get_open_trades(
    symbol: Optional[str] = Query(None),
    is_paper: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[TradeResponse]:
    """Retrieve all open trades / positions."""
    repo = TradeRepository(db)
    trades = await repo.get_open_trades(symbol=symbol, is_paper=is_paper)
    return [TradeResponse.model_validate(t) for t in trades]


@router.get("/stats", response_model=TradeStatistics)
async def get_trade_statistics(
    symbol: Optional[str] = Query(None),
    strategy_name: Optional[str] = Query(None),
    is_paper: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> TradeStatistics:
    """Retrieve aggregate performance metrics (win rate, profit factor, drawdown)."""
    repo = TradeRepository(db)
    return await repo.get_statistics(
        symbol=symbol, strategy_name=strategy_name, is_paper=is_paper
    )


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: str,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    """Get single trade by primary ID."""
    repo = TradeRepository(db)
    trade = await repo.get_by_id(trade_id)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with id '{trade_id}' not found.",
        )
    return TradeResponse.model_validate(trade)


@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_trade(
    trade_in: TradeCreate,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    """Record an opened trade and broadcast update."""
    repo = TradeRepository(db)
    trade = await repo.create(trade_in)

    # Broadcast via WebSocket
    await ws_manager.broadcast_trade_update(
        {
            "action": "opened",
            "trade": TradeResponse.model_validate(trade).model_dump(mode="json"),
        }
    )

    return TradeResponse.model_validate(trade)


@router.patch("/{trade_id}", response_model=TradeResponse)
async def update_trade(
    trade_id: str,
    trade_in: TradeUpdate,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    """Update stop loss, take profit, or parameters of a trade."""
    repo = TradeRepository(db)
    trade = await repo.update(trade_id, trade_in)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with id '{trade_id}' not found.",
        )

    await ws_manager.broadcast_trade_update(
        {
            "action": "updated",
            "trade": TradeResponse.model_validate(trade).model_dump(mode="json"),
        }
    )

    return TradeResponse.model_validate(trade)


@router.post("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: str,
    exit_price: float = Query(..., gt=0),
    pnl: float = Query(...),
    commission: float = Query(0.0),
    swap: float = Query(0.0),
    notes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    """Close an open trade with realized execution values."""
    repo = TradeRepository(db)
    trade = await repo.close_trade(
        trade_id=trade_id,
        exit_price=exit_price,
        pnl=pnl,
        commission=commission,
        swap=swap,
        notes=notes,
    )
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with id '{trade_id}' not found or already closed.",
        )

    await ws_manager.broadcast_trade_update(
        {
            "action": "closed",
            "trade": TradeResponse.model_validate(trade).model_dump(mode="json"),
        }
    )

    return TradeResponse.model_validate(trade)


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a trade record."""
    repo = TradeRepository(db)
    success = await repo.delete(trade_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with id '{trade_id}' not found.",
        )
