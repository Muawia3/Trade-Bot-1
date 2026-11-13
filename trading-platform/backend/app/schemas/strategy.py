"""
Pydantic v2 schemas for strategy configuration and management.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class StrategyConfigBase(BaseModel):
    """Base strategy configuration attributes."""
    name: str = Field(..., description="Unique strategy identifier name")
    symbol: Optional[str] = Field(None, description="Bound symbol or null for multi-symbol")
    enabled: bool = Field(True, description="Strategy execution active toggle")
    timeframe: str = Field("M15", description="Execution timeframe (e.g. M5, M15, H1)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy specific hyper-parameters")
    risk_percent: float = Field(1.0, gt=0, le=10.0, description="Risk percent per trade allocation")
    max_positions: int = Field(3, ge=1, le=20, description="Maximum concurrent positions allowed")


class StrategyConfigCreate(StrategyConfigBase):
    """Schema for registering a strategy configuration."""
    pass


class StrategyConfigUpdate(BaseModel):
    """Schema for updating strategy parameters and active state."""
    symbol: Optional[str] = None
    enabled: Optional[bool] = None
    timeframe: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    risk_percent: Optional[float] = Field(None, gt=0, le=10.0)
    max_positions: Optional[int] = Field(None, ge=1, le=20)


class StrategyToggle(BaseModel):
    """Quick enable/disable switch."""
    enabled: bool = Field(..., description="Active status toggle")


class StrategyConfigResponse(StrategyConfigBase):
    """Schema for returning strategy configuration details."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
