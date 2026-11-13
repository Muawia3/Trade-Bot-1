"""
Platform configuration and risk management settings endpoints.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import TradingMode, get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class RiskSettingsUpdate(BaseModel):
    """Schema for adjusting risk parameters."""
    default_risk_percent: float = Field(..., gt=0.0, le=10.0, description="Risk per trade %")
    max_daily_loss_percent: float = Field(..., gt=0.0, le=20.0, description="Max daily loss %")
    max_open_positions: int = Field(..., ge=1, le=20, description="Max concurrent open trades")
    max_drawdown_percent: float = Field(..., gt=0.0, le=50.0, description="Platform kill-switch drawdown %")


class TradingModeUpdate(BaseModel):
    """Schema for switching execution mode."""
    mode: str = Field(..., description="'paper', 'live', or 'backtest'")
    confirm_live: bool = Field(False, description="Must be true to authorize live capital risk")


@router.get("", response_model=Dict[str, Any])
async def get_platform_settings() -> Dict[str, Any]:
    """Retrieve non-sensitive platform configurations and operational parameters."""
    settings = get_settings()
    return {
        "trading_mode": settings.TRADING_MODE.value,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "default_risk_percent": settings.DEFAULT_RISK_PERCENT,
        "max_daily_loss_percent": settings.MAX_DAILY_LOSS_PERCENT,
        "max_open_positions": settings.MAX_OPEN_POSITIONS,
        "max_drawdown_percent": settings.MAX_DRAWDOWN_PERCENT,
        "paper_trading_initial_balance": settings.PAPER_TRADING_INITIAL_BALANCE,
        "paper_trading_currency": settings.PAPER_TRADING_CURRENCY,
        "mt5_configured": settings.mt5_configured,
        "ai_enabled": settings.AI_ENABLED,
        "pytorch_enabled": settings.PYTORCH_ENABLED,
        "debug": settings.DEBUG,
    }


@router.post("/trading-mode", response_model=Dict[str, Any])
async def update_trading_mode(payload: TradingModeUpdate) -> Dict[str, Any]:
    """
    Switch trading mode.
    Enforces strict safety check: Live trading cannot be enabled without explicit confirmation.
    """
    settings = get_settings()
    target_mode = payload.mode.lower()

    if target_mode not in ["paper", "live", "backtest"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid trading mode '{payload.mode}'. Must be 'paper', 'live', or 'backtest'.",
        )

    if target_mode == "live":
        if not payload.confirm_live:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Live trading requires confirm_live=True. Capital is at risk.",
            )
        if not settings.mt5_configured:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot switch to live trading: MT5 is not configured.",
            )
        settings.TRADING_MODE = TradingMode.LIVE
        settings.LIVE_TRADING_ENABLED = True
    elif target_mode == "paper":
        settings.TRADING_MODE = TradingMode.PAPER
        settings.LIVE_TRADING_ENABLED = False
    else:
        settings.TRADING_MODE = TradingMode.BACKTEST
        settings.LIVE_TRADING_ENABLED = False

    return {
        "status": "success",
        "current_mode": settings.TRADING_MODE.value,
        "live_enabled": settings.LIVE_TRADING_ENABLED,
    }


@router.patch("/risk", response_model=Dict[str, Any])
async def update_risk_settings(payload: RiskSettingsUpdate) -> Dict[str, Any]:
    """Update runtime server-side risk management thresholds."""
    settings = get_settings()
    settings.DEFAULT_RISK_PERCENT = payload.default_risk_percent
    settings.MAX_DAILY_LOSS_PERCENT = payload.max_daily_loss_percent
    settings.MAX_OPEN_POSITIONS = payload.max_open_positions
    settings.MAX_DRAWDOWN_PERCENT = payload.max_drawdown_percent

    return {
        "status": "success",
        "default_risk_percent": settings.DEFAULT_RISK_PERCENT,
        "max_daily_loss_percent": settings.MAX_DAILY_LOSS_PERCENT,
        "max_open_positions": settings.MAX_OPEN_POSITIONS,
        "max_drawdown_percent": settings.MAX_DRAWDOWN_PERCENT,
    }
