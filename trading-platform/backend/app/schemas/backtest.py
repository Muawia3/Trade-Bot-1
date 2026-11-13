"""
Pydantic v2 schemas for backtesting historical strategies and analyzing performance.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BacktestRequest(BaseModel):
    """Parameters required to trigger a backtest execution."""
    strategy_name: str = Field(..., description="Target strategy name")
    symbol: str = Field("XAUUSD", description="Symbol to backtest on")
    timeframe: str = Field("M15", description="Timeframe (M5, M15, H1, etc.)")
    start_date: datetime = Field(..., description="Start date of backtest window")
    end_date: datetime = Field(..., description="End date of backtest window")
    initial_balance: float = Field(10000.0, gt=0, description="Starting cash balance in USD")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom strategy parameter overrides")


class BacktestResultResponse(BaseModel):
    """Complete backtest output including equity curve and executed trades."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    parameters: Optional[Dict[str, Any]] = None
    trades_json: Optional[List[Dict[str, Any]]] = None
    equity_curve_json: Optional[List[Dict[str, Any]]] = None
    created_at: datetime


class BacktestSummaryResponse(BaseModel):
    """Lightweight summary of backtest results for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    created_at: datetime
