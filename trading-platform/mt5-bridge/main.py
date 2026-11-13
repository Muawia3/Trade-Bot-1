"""
FastAPI Microservice for MetaTrader 5 Bridge.
Provides REST and WebSocket interfaces for MT5 connectivity, symbol inspection,
market rate streaming, and risk-checked order execution.
"""

import sys
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import pandas as pd

# Ensure mt5-bridge root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config.bridge_config import get_bridge_config, BridgeConfig, TradingMode
from connector.mt5_connector import mt5_manager, mt5, _MT5_AVAILABLE
from connector.mock_mt5 import (
    mock_mt5_instance,
    TIMEFRAME_M1,
    TIMEFRAME_M5,
    TIMEFRAME_M15,
    TIMEFRAME_M30,
    TIMEFRAME_H1,
    TIMEFRAME_H4,
    TIMEFRAME_D1,
)
from services.symbol_service import symbol_service
from services.order_service import order_service

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("mt5_bridge.api")
config = get_bridge_config()


# =============================================================================
# WebSocket Connection & Subscription Manager
# =============================================================================

class PriceStreamManager:
    """Manages active WebSocket connections and their symbol subscriptions."""

    def __init__(self):
        self.active_connections: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._streaming_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            # Default subscription to target pairs
            self.active_connections[websocket] = {"XAUUSD", "EURUSD"}
        logger.info("New WebSocket price stream subscriber connected.")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                del self.active_connections[websocket]
        logger.info("WebSocket price stream client disconnected.")

    async def update_subscription(self, websocket: WebSocket, symbols: List[str]):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections[websocket] = set(s.upper() for s in symbols)

    async def broadcast_tick(self, symbol: str, tick_data: Dict[str, Any]):
        message = {"event": "price_tick", "symbol": symbol, "data": tick_data}
        dead_connections = []
        for ws, subs in list(self.active_connections.items()):
            if symbol.upper() in subs or "*" in subs:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead_connections.append(ws)

        for ws in dead_connections:
            await self.disconnect(ws)


stream_manager = PriceStreamManager()


async def background_tick_streamer():
    """Background loop polling ticks and pushing to active WebSocket clients."""
    logger.info("Starting background market tick streaming loop...")
    while True:
        try:
            if stream_manager.active_connections:
                # Collect all subscribed symbols across clients
                all_symbols: Set[str] = set()
                for subs in stream_manager.active_connections.values():
                    all_symbols.update(subs)

                for sym in all_symbols:
                    if sym == "*":
                        sym = "XAUUSD"
                    # Fetch tick
                    resolved = symbol_service.find_matching_symbol(sym) or sym
                    tick = None
                    if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
                        tick = mock_mt5_instance.symbol_info_tick(resolved)
                    else:
                        tick = mt5.symbol_info_tick(resolved)

                    if tick:
                        spread_points = int(round((tick.ask - tick.bid) / (0.01 if "XAU" in sym or "JPY" in sym else 0.00001)))
                        tick_payload = {
                            "symbol": sym,
                            "bid": round(tick.bid, 5 if "EUR" in sym else 2),
                            "ask": round(tick.ask, 5 if "EUR" in sym else 2),
                            "spread": spread_points,
                            "time": tick.time,
                            "iso_time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
                        }
                        await stream_manager.broadcast_tick(sym, tick_payload)

            await asyncio.sleep(0.5)  # 2 Hz stream rate
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in background tick streamer: %s", e)
            await asyncio.sleep(1.0)


# =============================================================================
# FastAPI Application & Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Initializing MetaTrader 5 Bridge on port %d...", config.BRIDGE_PORT)
    await mt5_manager.initialize()
    tick_task = asyncio.create_task(background_tick_streamer())
    yield
    tick_task.cancel()
    await mt5_manager.shutdown()
    logger.info("MetaTrader 5 Bridge shut down cleanly.")


app = FastAPI(
    title="MetaTrader 5 Bridge API",
    description="High-performance low-latency bridge microservice for MetaTrader 5 terminals.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request / Response Models
# =============================================================================

class OrderRequest(BaseModel):
    symbol: str
    side: str = Field(..., description="BUY or SELL")
    volume: float = Field(..., gt=0, description="Lot size (e.g. 0.01)")
    price: Optional[float] = Field(None, description="Optional entry price for limit/stop orders")
    sl: Optional[float] = Field(None, description="Stop Loss absolute price")
    tp: Optional[float] = Field(None, description="Take Profit absolute price")
    order_type: str = Field("market", description="market, limit, stop")
    deviation: int = Field(20, description="Slippage deviation in points")
    comment: str = Field("API Order", description="Order comment tag")


class PositionModifyRequest(BaseModel):
    sl: float = Field(..., description="New Stop Loss price")
    tp: float = Field(..., description="New Take Profit price")


class MarginCheckRequest(BaseModel):
    symbol: str
    volume: float = Field(..., gt=0)
    side: str = Field("BUY")


# =============================================================================
# REST Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint indicating MT5 connectivity status."""
    acc = await mt5_manager.get_account_info()
    return {
        "status": "healthy" if mt5_manager.is_connected else "disconnected",
        "mt5_connected": mt5_manager.is_connected,
        "mock_mode": mt5_manager.is_mock_mode,
        "trading_mode": config.TRADING_MODE.value,
        "live_trading_enabled": config.LIVE_TRADING_ENABLED,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "account_login": acc.get("login") if acc else None,
        "account_server": acc.get("server") if acc else None,
    }


@app.get("/account")
async def get_account():
    """Retrieve full account metrics."""
    acc = await mt5_manager.get_account_info()
    if not acc:
        raise HTTPException(status_code=503, detail="MT5 terminal or account info unavailable")
    return acc


@app.get("/symbols")
async def get_symbols():
    """List all discoverable broker symbols."""
    symbols = symbol_service.discover_symbols()
    return {"count": len(symbols), "symbols": symbols}


@app.get("/symbols/{symbol}")
async def get_symbol_detail(symbol: str = Path(..., description="Instrument symbol (e.g. XAUUSD, EURUSD)")):
    """Get full technical instrument specifications."""
    info = symbol_service.get_symbol_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    return info.to_dict()


@app.get("/prices/{symbol}")
async def get_current_price(symbol: str):
    """Retrieve live bid/ask/spread price tick."""
    resolved = symbol_service.find_matching_symbol(symbol) or symbol
    tick = None
    if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
        tick = mock_mt5_instance.symbol_info_tick(resolved)
    else:
        tick = mt5.symbol_info_tick(resolved)

    if not tick:
        raise HTTPException(status_code=404, detail=f"Current price for '{symbol}' unavailable")

    spread = int(round((tick.ask - tick.bid) / (0.01 if "XAU" in symbol or "JPY" in symbol else 0.00001)))
    return {
        "symbol": symbol,
        "resolved_symbol": resolved,
        "bid": tick.bid,
        "ask": tick.ask,
        "spread": spread,
        "time": tick.time,
        "iso_time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
    }


@app.get("/rates/{symbol}")
async def get_rates(
    symbol: str,
    timeframe: int = Query(60, description="Timeframe in minutes (1, 5, 15, 30, 60, 240, 1440)"),
    count: int = Query(100, ge=1, le=5000, description="Number of bars to fetch"),
    start_pos: int = Query(0, ge=0, description="Start offset (0 = latest)"),
):
    """Fetch historical OHLCV candle rates."""
    resolved = symbol_service.find_matching_symbol(symbol) or symbol
    rates = None

    if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
        rates = mock_mt5_instance.copy_rates_from_pos(resolved, timeframe, start_pos, count)
    else:
        rates = mt5.copy_rates_from_pos(resolved, timeframe, start_pos, count)

    if rates is None or len(rates) == 0:
        raise HTTPException(status_code=404, detail=f"No rate data returned for '{symbol}'")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(df),
        "candles": df.to_dict(orient="records"),
    }


@app.post("/orders")
async def place_order(order_req: OrderRequest):
    """
    Execute a new order.
    Strictly verifies safety constraints and isolates paper trading from real money.
    """
    result = order_service.send_order(
        symbol=order_req.symbol,
        side=order_req.side,
        volume=order_req.volume,
        price=order_req.price,
        sl=order_req.sl,
        tp=order_req.tp,
        order_type=order_req.order_type,
        deviation=order_req.deviation,
        comment=order_req.comment,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.to_dict())
    return result.to_dict()


@app.put("/orders/{ticket}")
async def modify_order(
    ticket: int = Path(..., description="Position ticket ID"),
    req: PositionModifyRequest = ...,
):
    """Modify position Stop Loss and Take Profit levels."""
    result = order_service.modify_position(ticket=ticket, sl=req.sl, tp=req.tp)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.to_dict())
    return result.to_dict()


@app.delete("/orders/{ticket}")
async def close_position(
    ticket: int = Path(..., description="Position ticket ID"),
    volume: Optional[float] = Query(None, description="Volume to close, or None for entire position"),
):
    """Close position."""
    result = order_service.close_position(ticket=ticket, volume=volume)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.to_dict())
    return result.to_dict()


@app.get("/positions")
async def get_open_positions(symbol: Optional[str] = Query(None)):
    """Retrieve all open positions."""
    positions = order_service.get_open_positions(symbol=symbol)
    return {"count": len(positions), "positions": positions}


@app.get("/orders/pending")
async def get_pending_orders(symbol: Optional[str] = Query(None)):
    """Retrieve pending orders."""
    orders = order_service.get_pending_orders(symbol=symbol)
    return {"count": len(orders), "orders": orders}


@app.get("/history")
async def get_trade_history():
    """Retrieve executed trade history."""
    history = order_service.get_trade_history()
    return {"count": len(history), "trades": history}


@app.post("/margin/check")
async def check_margin(req: MarginCheckRequest):
    """Perform pre-trade margin check."""
    status = order_service.check_margin(symbol=req.symbol, volume=req.volume, side=req.side)
    return status.to_dict()


# =============================================================================
# WebSocket Endpoint for Price Streaming
# =============================================================================

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for real-time live price streaming."""
    await stream_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "subscribe":
                symbols = data.get("symbols", [])
                await stream_manager.update_subscription(websocket, symbols)
                await websocket.send_json({"status": "subscribed", "symbols": symbols})
            elif action == "ping":
                await websocket.send_json({"status": "pong", "time": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        await stream_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket connection error: %s", e)
        await stream_manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.BRIDGE_HOST,
        port=config.BRIDGE_PORT,
        reload=config.DEBUG,
    )
