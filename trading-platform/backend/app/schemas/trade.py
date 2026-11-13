"""
Pydantic v2 schemas for trade execution, tracking, and reporting.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TradeBase(BaseModel):
    """Shared trade attributes."""
    symbol: str = Field(..., description="Trading pair or asset symbol (e.g. XAUUSD, EURUSD)")
    side: str = Field(..., description="Order side: 'buy' or 'sell'")
    entry_price: float = Field(..., gt=0, description="Execution entry price")
    volume: float = Field(..., gt=0, description="Position volume in lots")
    stop_loss: Optional[float] = Field(None, gt=0, description="Stop loss price level")
    take_profit: Optional[float] = Field(None, gt=0, description="Take profit price level")
    strategy_name: Optional[str] = Field(None, description="Generating strategy name")
    signal_id: Optional[str] = Field(None, description="Linked signal identifier")
    is_paper: bool = Field(True, description="Whether this is a paper/simulated trade")
    notes: Optional[str] = Field(None, description="Additional execution notes")


class TradeCreate(TradeBase):
    """Schema for opening a new trade."""
    opened_at: Optional[datetime] = Field(None, description="Timestamp trade was opened")


class TradeUpdate(BaseModel):
    """Schema for modifying or closing an existing trade."""
    exit_price: Optional[float] = Field(None, gt=0, description="Price at which trade was closed")
    stop_loss: Optional[float] = Field(None, gt=0, description="Updated stop loss level")
    take_profit: Optional[float] = Field(None, gt=0, description="Updated take profit level")
    status: Optional[str] = Field(None, description="Updated status ('open', 'closed', 'cancelled')")
    pnl: Optional[float] = Field(None, description="Realized profit or loss in account currency")
    commission: Optional[float] = Field(None, description="Broker commission fee")
    swap: Optional[float] = Field(None, description="Overnight swap fee")
    closed_at: Optional[datetime] = Field(None, description="Closing timestamp")
    notes: Optional[str] = Field(None, description="Updated notes")


class TradeResponse(TradeBase):
    """Schema for trade output responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    exit_price: Optional[float] = None
    status: str
    pnl: float
    commission: float
    swap: float
    opened_at: datetime
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TradeFilter(BaseModel):
    """Filter parameters for querying trade history."""
    symbol: Optional[str] = None
    status: Optional[str] = None
    strategy_name: Optional[str] = None
    is_paper: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class TradeStatistics(BaseModel):
    """Performance statistics across a set of trades."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    profit_factor: float
    gross_profit: float
    gross_loss: float
    average_trade: float
    max_drawdown: float
