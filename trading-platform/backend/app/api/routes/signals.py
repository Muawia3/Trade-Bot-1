"""
Signals API endpoints for strategy triggers, AI confidence scoring, and queue state.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.repositories.signal_repository import SignalRepository
from app.schemas.signal import (
    SignalCreate,
    SignalFilter,
    SignalResponse,
    SignalUpdate,
)
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=Dict[str, Any])
async def list_signals(
    symbol: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None),
    strategy_name: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    acted_on: Optional[bool] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve filtered signals history with pagination."""
    repo = SignalRepository(db)
    filters = SignalFilter(
        symbol=symbol,
        signal_type=signal_type,
        strategy_name=strategy_name,
        timeframe=timeframe,
        acted_on=acted_on,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    signals, total = await repo.get_multi(filters)
    return {
        "items": [SignalResponse.model_validate(s) for s in signals],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/active", response_model=List[SignalResponse])
async def get_active_signals(
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[SignalResponse]:
    """Retrieve unexpired, unacted signals ready for execution consideration."""
    repo = SignalRepository(db)
    signals = await repo.get_active_signals(symbol=symbol)
    return [SignalResponse.model_validate(s) for s in signals]


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """Retrieve a single signal by ID."""
    repo = SignalRepository(db)
    signal = await repo.get_by_id(signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with id '{signal_id}' not found.",
        )
    return SignalResponse.model_validate(signal)


@router.post("", response_model=SignalResponse, status_code=status.HTTP_201_CREATED)
async def create_signal(
    signal_in: SignalCreate,
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """
    Ingest a new trade signal.
    Ensures reasoning is included and broadcasts via WebSocket.
    """
    if not signal_in.reasoning:
        signal_in.reasoning = (
            f"Automated signal from {signal_in.strategy_name} on {signal_in.symbol} "
            f"with confidence {signal_in.confidence:.2f}."
        )

    repo = SignalRepository(db)
    signal = await repo.create(signal_in)

    # Broadcast to live subscribers
    signal_resp = SignalResponse.model_validate(signal)
    await ws_manager.broadcast_signal(signal_resp.model_dump(mode="json"))

    return signal_resp


@router.patch("/{signal_id}", response_model=SignalResponse)
async def update_signal(
    signal_id: str,
    signal_in: SignalUpdate,
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """Update signal status or expiration."""
    repo = SignalRepository(db)
    signal = await repo.update(signal_id, signal_in)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with id '{signal_id}' not found.",
        )
    return SignalResponse.model_validate(signal)


@router.post("/{signal_id}/act", response_model=SignalResponse)
async def act_on_signal(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """Mark a signal as acted upon after executing an order."""
    repo = SignalRepository(db)
    signal = await repo.mark_acted_on(signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with id '{signal_id}' not found.",
        )
    return SignalResponse.model_validate(signal)
