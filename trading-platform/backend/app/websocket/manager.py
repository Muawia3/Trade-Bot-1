"""
WebSocket Connection Manager supporting room-based subscriptions and topic broadcasting.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active client WebSocket connections and room-based topic subscriptions.
    Rooms can be subscribed per-symbol (e.g., 'ticks:XAUUSD'), per-candle ('candles:EURUSD:M15'),
    or by functional event channels ('signals', 'trades', 'account').
    """

    def __init__(self) -> None:
        # All currently connected WebSocket clients
        self.active_connections: Set[WebSocket] = set()
        # Mapping: room_name -> Set of subscribed WebSockets
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # Lock for thread-safe/asyncio subscription modifications
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept an incoming connection and register it."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(
            "WebSocket client connected. Total active connections: %d",
            len(self.active_connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected client from all active sets and rooms."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            # Clean from all rooms
            for room_name, clients in list(self.rooms.items()):
                if websocket in clients:
                    clients.remove(websocket)
                if not clients:
                    self.rooms.pop(room_name, None)

        logger.info(
            "WebSocket client disconnected. Total active connections: %d",
            len(self.active_connections),
        )

    async def subscribe(self, websocket: WebSocket, room: str) -> None:
        """Add a client to a specific broadcast room."""
        async with self._lock:
            if room not in self.rooms:
                self.rooms[room] = set()
            self.rooms[room].add(websocket)
        logger.debug("Client subscribed to room: %s", room)

    async def unsubscribe(self, websocket: WebSocket, room: str) -> None:
        """Remove a client from a specific room."""
        async with self._lock:
            if room in self.rooms and websocket in self.rooms[room]:
                self.rooms[room].remove(websocket)
                if not self.rooms[room]:
                    del self.rooms[room]
        logger.debug("Client unsubscribed from room: %s", room)

    async def broadcast_to_all(self, message: Dict[str, Any]) -> None:
        """Broadcast a JSON message to all connected clients."""
        if not self.active_connections:
            return

        payload = json.dumps(message)
        dead_connections: List[WebSocket] = []

        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.debug("Error sending broadcast to client: %s", exc)
                dead_connections.append(connection)

        for dead in dead_connections:
            await self.disconnect(dead)

    async def broadcast_to_room(self, room: str, message: Dict[str, Any]) -> None:
        """Broadcast a message only to clients subscribed to the given room."""
        clients = self.rooms.get(room)
        if not clients:
            return

        payload = json.dumps(message)
        dead_connections: List[WebSocket] = []

        for connection in list(clients):
            try:
                await connection.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.debug("Error sending to room %s: %s", room, exc)
                dead_connections.append(connection)

        for dead in dead_connections:
            await self.disconnect(dead)

    # ── Convenience Broadcast Methods ──

    async def broadcast_tick(self, symbol: str, tick_data: Dict[str, Any]) -> None:
        """Broadcast real-time tick to symbol-specific and global market channels."""
        msg = {
            "type": "tick",
            "symbol": symbol.upper(),
            "data": tick_data,
        }
        await self.broadcast_to_room(f"ticks:{symbol.upper()}", msg)
        await self.broadcast_to_room("market_data", msg)

    async def broadcast_candle(
        self, symbol: str, timeframe: str, candle_data: Dict[str, Any]
    ) -> None:
        """Broadcast updated candle to subscribers."""
        msg = {
            "type": "candle",
            "symbol": symbol.upper(),
            "timeframe": timeframe.upper(),
            "data": candle_data,
        }
        await self.broadcast_to_room(
            f"candles:{symbol.upper()}:{timeframe.upper()}", msg
        )
        await self.broadcast_to_room("market_data", msg)

    async def broadcast_signal(self, signal_data: Dict[str, Any]) -> None:
        """Broadcast new actionable signal to signal room and general broadcast."""
        msg = {
            "type": "signal",
            "data": signal_data,
        }
        await self.broadcast_to_room("signals", msg)
        await self.broadcast_to_all(msg)

    async def broadcast_trade_update(self, trade_data: Dict[str, Any]) -> None:
        """Broadcast trade execution/close update."""
        msg = {
            "type": "trade_update",
            "data": trade_data,
        }
        await self.broadcast_to_room("trades", msg)

    async def broadcast_account_update(self, account_data: Dict[str, Any]) -> None:
        """Broadcast balance/equity/margin change."""
        msg = {
            "type": "account_update",
            "data": account_data,
        }
        await self.broadcast_to_room("account", msg)


# Global singleton instance
ws_manager = ConnectionManager()
