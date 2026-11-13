"""
Health check and platform status API endpoints.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.database.connection import check_database_health

router = APIRouter(prefix="/health", tags=["system"])


@router.get("", status_code=status.HTTP_200_OK, response_model=Dict[str, Any])
async def get_health_status() -> Dict[str, Any]:
    """
    Returns platform health, database connectivity, and core operational flags.
    """
    settings = get_settings()
    db_healthy = await check_database_health()

    overall_status = "healthy" if db_healthy else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": "connected" if db_healthy else "disconnected",
            "healthy": db_healthy,
        },
        "platform": {
            "trading_mode": settings.TRADING_MODE.value,
            "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
            "mt5_configured": settings.mt5_configured,
            "ai_enabled": settings.AI_ENABLED,
            "debug": settings.DEBUG,
        },
    }
