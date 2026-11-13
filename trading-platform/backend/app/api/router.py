"""
Master API router aggregating all modular route endpoints.
"""

from fastapi import APIRouter

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

api_router = APIRouter()

# Register REST endpoints
api_router.include_router(health.router)
api_router.include_router(account.router)
api_router.include_router(market_data.router)
api_router.include_router(trades.router)
api_router.include_router(signals.router)
api_router.include_router(strategies.router)
api_router.include_router(backtesting.router)
api_router.include_router(paper_trading.router)
api_router.include_router(settings.router)

# Register WebSocket endpoints
api_router.include_router(websocket_routes.router)
