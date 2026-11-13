"""
Real-time Market Price Feed Engine.
Maintains persistent WebSocket connection to the MT5 Bridge microservice,
stores price history in bounded ring buffers, and broadcasts live streaming
ticks to registered frontend WebSocket subscribers and trading strategies.
"""

import os
import json
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Awaitable, Any, Set
import websockets

logger = logging.getLogger("market_data.price_feed")


class PriceHistoryBuffer:
    """
    In-memory bounded ring buffer storing rolling price ticks for each symbol.
    Provides rapid retrieval of recent tick arrays for micro-volatility and charting.
    """

    def __init__(self, max_ticks_per_symbol: int = 1000):
        self.max_ticks = max_ticks_per_symbol
        self._buffers: Dict[str, deque] = {}

    def add_tick(self, symbol: str, tick_data: Dict[str, Any]) -> None:
        """Append tick to ring buffer."""
        sym = symbol.upper()
        if sym not in self._buffers:
            self._buffers[sym] = deque(maxlen=self.max_ticks)
        self._buffers[sym].append(tick_data)

    def get_recent_ticks(self, symbol: str, count: int = 50) -> List[Dict[str, Any]]:
        """Retrieve the last N ticks for a symbol."""
        sym = symbol.upper()
        if sym not in self._buffers:
            return []
        buf = self._buffers[sym]
        slice_count = min(count, len(buf))
        return list(buf)[-slice_count:]

    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return the most recent tick for symbol."""
        sym = symbol.upper()
        if sym not in self._buffers or not self._buffers[sym]:
            return None
        return self._buffers[sym][-1]

    def clear(self, symbol: Optional[str] = None) -> None:
        """Clear buffer for a symbol or all symbols."""
        if symbol:
            sym = symbol.upper()
            if sym in self._buffers:
                self._buffers[sym].clear()
        else:
            self._buffers.clear()


class PriceFeed:
    """
    Asynchronous Price Feed listener connecting to MT5 Bridge microservice.
    Dispatches incoming price ticks to registered callbacks (e.g. backend WebSocket manager).
    """

    def __init__(self, bridge_ws_url: Optional[str] = None):
        self.bridge_ws_url = bridge_ws_url or os.getenv("MT5_BRIDGE_WS_URL", "ws://localhost:8001/ws/prices")
        self.ring_buffer = PriceHistoryBuffer(max_ticks_per_symbol=1000)
        self._subscribed_symbols: Set[str] = {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY"}
        self._listeners: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._ws: Optional[Any] = None

    def register_listener(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Attach a subscriber callback for price broadcasts."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Remove a subscriber callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def subscribe(self, symbol: str) -> None:
        """Add symbol to streaming subscription set."""
        sym = symbol.upper()
        self._subscribed_symbols.add(sym)
        if self._ws:
            asyncio.create_task(self._send_subscription())

    def unsubscribe(self, symbol: str) -> None:
        """Remove symbol from subscription set."""
        sym = symbol.upper()
        self._subscribed_symbols.discard(sym)
        if self._ws:
            asyncio.create_task(self._send_subscription())

    async def _send_subscription(self) -> None:
        """Send current symbol subscriptions to MT5 bridge."""
        if self._ws:
            try:
                payload = {
                    "action": "subscribe",
                    "symbols": list(self._subscribed_symbols),
                }
                await self._ws.send(json.dumps(payload))
            except Exception as e:
                logger.error("Failed to send subscription update to MT5 bridge: %s", e)

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        """Fan out tick data to all registered listeners."""
        for callback in self._listeners:
            try:
                await callback(message)
            except Exception as e:
                logger.error("Error executing price feed listener callback: %s", e)

    async def _run_stream_loop(self) -> None:
        """Continuous connection and streaming loop with exponential backoff."""
        backoff = 1.0
        max_backoff = 30.0

        while self._running:
            try:
                logger.info("Connecting to MT5 Bridge price feed at %s...", self.bridge_ws_url)
                async with websockets.connect(self.bridge_ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    backoff = 1.0
                    logger.info("Connected to MT5 Bridge WebSocket price stream.")

                    # Send initial symbol subscriptions
                    await self._send_subscription()

                    while self._running:
                        msg_raw = await ws.recv()
                        try:
                            msg = json.loads(msg_raw)
                        except json.JSONDecodeError:
                            continue

                        event = msg.get("event")
                        if event == "price_tick":
                            symbol = msg.get("symbol", "")
                            data = msg.get("data", {})
                            if symbol and data:
                                # Store in ring buffer
                                self.ring_buffer.add_tick(symbol, data)
                                # Broadcast to frontend / subscribers
                                await self._broadcast({
                                    "type": "market_tick",
                                    "symbol": symbol,
                                    "data": data,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                })

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._ws = None
                if self._running:
                    logger.warning("Price feed connection dropped or bridge unavailable (%s). Retrying in %.1fs...", e, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, max_backoff)

    def start(self) -> asyncio.Task:
        """Start price feed background listener."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_stream_loop())
            logger.info("Market Price Feed service started.")
        return self._task

    async def stop(self) -> None:
        """Stop price feed background listener."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Market Price Feed service stopped.")


# Singleton price feed instance
price_feed = PriceFeed()
