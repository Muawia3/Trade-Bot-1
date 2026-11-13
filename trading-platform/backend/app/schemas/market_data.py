"""
Pydantic v2 schemas for market data: OHLCV candles, ticks, and live prices.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CandleDataBase(BaseModel):
    """Base candle data attributes."""
    symbol: str = Field(..., description="Asset symbol (e.g. XAUUSD)")
    timeframe: str = Field(..., description="Timeframe string (M1, M5, M15, H1, H4, D1)")
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price")
    low: float = Field(..., gt=0, description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: float = Field(0.0, ge=0.0, description="Tick or real volume")
    spread: Optional[float] = Field(0.0, ge=0.0, description="Spread in points/pips")
    timestamp: datetime = Field(..., description="Candle start timestamp (UTC)")


class CandleDataCreate(CandleDataBase):
    """Schema for inserting a new candle."""
    pass


class CandleDataResponse(CandleDataBase):
    """Schema for returning candle data."""
    model_config = ConfigDict(from_attributes=True)

    id: str


class CandleBulkCreate(BaseModel):
    """Schema for bulk inserting candles."""
    candles: List[CandleDataCreate]


class TickDataBase(BaseModel):
    """Base tick quote attributes."""
    symbol: str = Field(..., description="Asset symbol")
    bid: float = Field(..., gt=0, description="Current bid price")
    ask: float = Field(..., gt=0, description="Current ask price")
    volume: float = Field(0.0, ge=0.0, description="Tick volume")
    timestamp: datetime = Field(..., description="Tick timestamp (UTC)")


class TickDataCreate(TickDataBase):
    """Schema for recording a new tick quote."""
    pass


class TickDataResponse(TickDataBase):
    """Schema for returning tick quote."""
    model_config = ConfigDict(from_attributes=True)

    id: str


class CurrentPriceResponse(BaseModel):
    """Live snapshot of bid, ask, and spread for a symbol."""
    symbol: str
    bid: float
    ask: float
    spread: float
    timestamp: datetime
    is_live: bool = True


class SymbolInfoResponse(BaseModel):
    """Specification details for a tradeable instrument."""
    symbol: str
    description: Optional[str] = None
    currency_base: Optional[str] = None
    currency_profit: Optional[str] = None
    digits: int = 2
    point: float = 0.01
    contract_size: float = 100.0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    spread: float = 0.0
    trade_mode: str = "full"
