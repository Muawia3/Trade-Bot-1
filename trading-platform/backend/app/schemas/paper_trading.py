"""
Pydantic v2 schemas for paper trading accounts, positions, and orders.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PaperAccountCreate(BaseModel):
    """Schema for initializing a paper trading account."""
    name: str = Field("Default Paper Account", description="Account label")
    initial_balance: float = Field(10000.0, gt=0, description="Starting virtual balance")
    currency: str = Field("USD", description="Account currency")


class PaperAccountUpdate(BaseModel):
    """Schema for updating paper account settings."""
    name: Optional[str] = None
    current_balance: Optional[float] = Field(None, ge=0.0)
    equity: Optional[float] = Field(None, ge=0.0)


class PaperAccountReset(BaseModel):
    """Schema for resetting paper trading account balance and clearing positions."""
    initial_balance: float = Field(10000.0, gt=0, description="New starting balance")


class PaperAccountResponse(BaseModel):
    """Schema for returning paper account state."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    initial_balance: float
    current_balance: float
    equity: float
    currency: str
    created_at: datetime


class PaperPositionResponse(BaseModel):
    """Schema representing an open paper position."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    symbol: str
    side: str
    volume: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: float
    opened_at: datetime


class PaperPositionCloseRequest(BaseModel):
    """Request to close an open paper position."""
    exit_price: Optional[float] = Field(None, description="Explicit exit price or current market price if omitted")


class PaperOrderCreate(BaseModel):
    """Schema for submitting a simulated paper order."""
    symbol: str = Field(..., description="Target symbol")
    side: str = Field(..., description="'buy' or 'sell'")
    volume: float = Field(..., gt=0, description="Order volume in lots")
    order_type: str = Field("market", description="'market', 'limit', or 'stop'")
    price: float = Field(..., gt=0, description="Execution or trigger price")
    stop_loss: Optional[float] = Field(None, gt=0, description="Optional stop loss")
    take_profit: Optional[float] = Field(None, gt=0, description="Optional take profit")


class PaperOrderResponse(BaseModel):
    """Schema representing a simulated paper order."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    symbol: str
    side: str
    volume: float
    order_type: str
    price: float
    status: str
    created_at: datetime


class PaperTradingStatus(BaseModel):
    """Aggregated status overview for paper trading."""
    account: PaperAccountResponse
    open_positions: List[PaperPositionResponse]
    pending_orders: List[PaperOrderResponse]
    unrealized_pnl: float = 0.0
    margin_used: float = 0.0
    free_margin: float = 0.0
