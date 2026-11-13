"""
API route modules package.
"""

from app.api.routes import (
    account,
    backtesting,
    health,
    market_data,
    paper_trading,
    settings,
    signals,
    strategies,
    trades,
    websocket_routes,
)

__all__ = [
    "account",
    "backtesting",
    "health",
    "market_data",
    "paper_trading",
    "settings",
    "signals",
    "strategies",
    "trades",
    "websocket_routes",
]
