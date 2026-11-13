"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings, TradingMode
from app.core.logging_config import setup_logging
from app.core.constants import API_V1_PREFIX

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()

    # ── Startup ──
    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)

    logger.info("=" * 60)
    logger.info("  AI Forex & Gold Trading Platform")
    logger.info("=" * 60)
    logger.info("  Trading Mode  : %s", settings.TRADING_MODE.value.upper())
    logger.info("  Debug         : %s", settings.DEBUG)
    logger.info("  API           : http://%s:%s", settings.API_HOST, settings.API_PORT)
    logger.info("  MT5 Configured: %s", settings.mt5_configured)
    logger.info("  AI Enabled    : %s", settings.AI_ENABLED)
    if settings.is_paper_trading:
        logger.info(
            "  Paper Balance : %s %s",
            settings.PAPER_TRADING_INITIAL_BALANCE,
            settings.PAPER_TRADING_CURRENCY,
        )
    if settings.is_live_trading:
        logger.warning("  ⚠  LIVE TRADING IS ENABLED — REAL MONEY AT RISK")
    logger.info("=" * 60)

    # ── Database Pool ──
    from app.database.connection import close_db

    yield

    # ── Shutdown ──
    logger.info("Shutting down Trading Platform…")
    await close_db()


def create_app() -> FastAPI:
    """Factory function to create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AI Forex & Gold Trading Platform",
        description="Professional trading platform with MT5 integration, AI-powered signals, and comprehensive risk management.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health Check ──
    @app.get("/health", tags=["system"])
    async def health_check():
        return {
            "status": "healthy",
            "trading_mode": settings.TRADING_MODE.value,
            "mt5_configured": settings.mt5_configured,
            "ai_enabled": settings.AI_ENABLED,
        }

    # ── Routers ──
    from app.api.router import api_router
    from app.api.routes.websocket_routes import router as ws_router

    app.include_router(api_router, prefix=API_V1_PREFIX)
    app.include_router(ws_router)  # Also expose /ws/live and /ws/market-data/{symbol} at root level

    return app


# Application instance
app = create_app()
