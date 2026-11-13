"""
Pydantic v2 schemas for trading signals and indicators snapshots.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class SignalBase(BaseModel):
    """Shared signal attributes."""
    symbol: str = Field(..., description="Target trading pair (e.g. XAUUSD, EURUSD)")
    signal_type: str = Field(..., description="Direction: 'BUY', 'SELL', or 'HOLD'")
    strategy_name: str = Field(..., description="Strategy that computed the signal")
    timeframe: str = Field("M15", description="Analysis timeframe (M1, M5, M15, H1, H4, D1)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence metric from 0.0 to 1.0")
    entry_price: float = Field(..., gt=0, description="Recommended entry price")
    stop_loss: Optional[float] = Field(None, gt=0, description="Suggested stop loss level")
    take_profit: Optional[float] = Field(None, gt=0, description="Suggested take profit level")
    indicators_snapshot: Optional[Dict[str, Any]] = Field(
        None, description="Snapshot of technical indicator values at trigger time"
    )
    reasoning: Optional[str] = Field(None, description="Detailed explanation or rule triggers")


class SignalCreate(SignalBase):
    """Schema for generating and persisting a new signal."""
    expired_at: Optional[datetime] = Field(None, description="Timestamp after which signal is invalid")


class SignalUpdate(BaseModel):
    """Schema for updating signal status (e.g. marking as acted on)."""
    acted_on: Optional[bool] = Field(None, description="Whether an order was executed for this signal")
    expired_at: Optional[datetime] = Field(None, description="Updated expiration timestamp")
    reasoning: Optional[str] = Field(None, description="Updated or appended reasoning")


class SignalResponse(SignalBase):
    """Schema for returning signal details."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    expired_at: Optional[datetime] = None
    acted_on: bool


class SignalFilter(BaseModel):
    """Query filters for signal history and active queue."""
    symbol: Optional[str] = None
    signal_type: Optional[str] = None
    strategy_name: Optional[str] = None
    timeframe: Optional[str] = None
    acted_on: Optional[bool] = None
    active_only: bool = Field(False, description="Filter for unexpired, unacted signals")
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
