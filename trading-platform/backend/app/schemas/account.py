"""
Pydantic v2 schemas for MT5 and system accounts.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AccountBase(BaseModel):
    """Shared account attributes."""
    mt5_login: Optional[int] = Field(None, description="MetaTrader 5 login account number")
    broker: Optional[str] = Field(None, description="Broker or firm name")
    server: Optional[str] = Field(None, description="Access server name")
    account_type: str = Field("demo", description="Type: 'demo', 'real', or 'paper'")
    currency: str = Field("USD", description="Base account currency")
    leverage: int = Field(100, gt=0, description="Account leverage ratio (e.g. 100 for 1:100)")
    balance: float = Field(0.0, ge=0.0, description="Current realized balance")
    equity: float = Field(0.0, ge=0.0, description="Current equity including floating PnL")
    is_demo: bool = Field(True, description="Flag indicating demo vs live real account")


class AccountCreate(AccountBase):
    """Schema for registering a new trading account."""
    pass


class AccountUpdate(BaseModel):
    """Schema for synchronizing balance, equity, or account parameters."""
    broker: Optional[str] = None
    server: Optional[str] = None
    account_type: Optional[str] = None
    leverage: Optional[int] = Field(None, gt=0)
    balance: Optional[float] = Field(None, ge=0.0)
    equity: Optional[float] = Field(None, ge=0.0)
    is_demo: Optional[bool] = None


class AccountResponse(AccountBase):
    """Schema for returning account details."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class AccountOverview(BaseModel):
    """Comprehensive portfolio and margin overview."""
    account_id: str
    account_type: str
    currency: str
    balance: float
    equity: float
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_daily_pnl: float = 0.0
    open_positions_count: int = 0
    is_connected: bool = False
