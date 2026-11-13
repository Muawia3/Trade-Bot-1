"""
Market data API endpoints for OHLCV candles, ticks, and instrument prices.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FOREX_PAIRS, GOLD_INSTRUMENTS, TARGET_INSTRUMENTS
from app.database.connection import get_db
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.market_data import (
    CandleBulkCreate,
    CandleDataCreate,
    CandleDataResponse,
    CurrentPriceResponse,
    SymbolInfoResponse,
    TickDataCreate,
    TickDataResponse,
)
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.get("/symbols", response_model=List[str])
async def get_supported_symbols() -> List[str]:
    """Return all configured target trading pairs and commodities."""
    return TARGET_INSTRUMENTS


@router.get("/symbols/{symbol}/info", response_model=SymbolInfoResponse)
async def get_symbol_info(symbol: str) -> SymbolInfoResponse:
    """
    Get contract size, pip precision, and trading constraints for a symbol.
    """
    sym = symbol.upper()
    if sym not in TARGET_INSTRUMENTS and not any(sym.startswith(p) for p in TARGET_INSTRUMENTS):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol}' not supported.",
        )

    # Dynamic symbol specification
    if "XAU" in sym:
        digits = 2
        point = 0.01
        contract_size = 100.0  # 100 oz per standard lot
        description = "Gold vs US Dollar"
    elif "XAG" in sym:
        digits = 3
        point = 0.001
        contract_size = 5000.0
        description = "Silver vs US Dollar"
    elif "JPY" in sym:
        digits = 3
        point = 0.001
        contract_size = 100000.0
        description = f"{sym[:3]} vs {sym[3:]}"
    else:
        digits = 5
        point = 0.00001
        contract_size = 100000.0
        description = f"{sym[:3]} vs {sym[3:]}"

    return SymbolInfoResponse(
        symbol=sym,
        description=description,
        currency_base=sym[:3],
        currency_profit=sym[3:],
        digits=digits,
        point=point,
        contract_size=contract_size,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        spread=1.5 if "XAU" in sym else 0.8,
        trade_mode="full",
    )


@router.get("/candles", response_model=List[CandleDataResponse])
async def get_candles(
    symbol: str = Query(..., description="Symbol, e.g. XAUUSD"),
    timeframe: str = Query("M15", description="Timeframe, e.g. M1, M5, M15, H1, H4, D1"),
    start_date: Optional[datetime] = Query(None, description="Start date ISO 8601"),
    end_date: Optional[datetime] = Query(None, description="End date ISO 8601"),
    limit: int = Query(300, ge=1, le=2000, description="Max candles to return"),
    db: AsyncSession = Depends(get_db),
) -> List[CandleDataResponse]:
    """Query chronological candlestick history."""
    repo = MarketDataRepository(db)
    candles = await repo.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return [CandleDataResponse.model_validate(c) for c in candles]


@router.post("/candles/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_insert_candles(
    payload: CandleBulkCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store or update a batch of OHLCV candles."""
    repo = MarketDataRepository(db)
    count = await repo.upsert_candles(payload.candles)
    return {"status": "success", "upserted_count": count}


@router.get("/prices/{symbol}", response_model=CurrentPriceResponse)
async def get_current_price(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> CurrentPriceResponse:
    """
    Get current market quote for an instrument.
    Queries the latest tick or candle close.
    """
    sym = symbol.upper()
    repo = MarketDataRepository(db)
    latest_tick = await repo.get_latest_tick(sym)

    if latest_tick:
        return CurrentPriceResponse(
            symbol=sym,
            bid=latest_tick.bid,
            ask=latest_tick.ask,
            spread=round(latest_tick.ask - latest_tick.bid, 4),
            timestamp=latest_tick.timestamp,
            is_live=True,
        )

    # Fallback to latest candle close
    latest_candle = await repo.get_latest_candle(sym, "M1")
    if not latest_candle:
        latest_candle = await repo.get_latest_candle(sym, "M15")

    if latest_candle:
        spread_val = latest_candle.spread or 0.0
        return CurrentPriceResponse(
            symbol=sym,
            bid=latest_candle.close,
            ask=round(latest_candle.close + spread_val, 4),
            spread=spread_val,
            timestamp=latest_candle.timestamp,
            is_live=False,
        )

    # Mock baseline fallback for initial start before data ingestion
    default_price = 2650.0 if "XAU" in sym else 1.0850
    return CurrentPriceResponse(
        symbol=sym,
        bid=default_price,
        ask=round(default_price + (0.20 if "XAU" in sym else 0.00015), 5),
        spread=0.20 if "XAU" in sym else 0.00015,
        timestamp=datetime.now(timezone.utc),
        is_live=False,
    )


@router.post("/ticks", response_model=TickDataResponse, status_code=status.HTTP_201_CREATED)
async def record_tick(
    tick_in: TickDataCreate,
    db: AsyncSession = Depends(get_db),
) -> TickDataResponse:
    """Ingest a tick quote and broadcast to live subscribers."""
    repo = MarketDataRepository(db)
    tick = await repo.add_tick(tick_in)

    # Broadcast via WebSocket
    await ws_manager.broadcast_tick(
        symbol=tick.symbol,
        tick_data={
            "bid": tick.bid,
            "ask": tick.ask,
            "volume": tick.volume,
            "timestamp": tick.timestamp.isoformat(),
        },
    )

    return TickDataResponse.model_validate(tick)
