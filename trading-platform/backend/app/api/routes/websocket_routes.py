"""
WebSocket route handlers for streaming ticks, candles, signals, and trade notifications.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket) -> None:
    """
    Main WebSocket endpoint for client connections.
    Supports room subscriptions via incoming action messages:
      - {"action": "subscribe", "room": "ticks:XAUUSD"}
      - {"action": "unsubscribe", "room": "ticks:XAUUSD"}
      - {"action": "ping"} -> responds {"type": "pong"}
    """
    await ws_manager.connect(websocket)
    try:
        # Auto-subscribe to fundamental events
        await ws_manager.subscribe(websocket, "signals")
        await ws_manager.subscribe(websocket, "trades")
        await ws_manager.subscribe(websocket, "account")

        # Welcome handshake
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_established",
                    "message": "Connected to Trading Platform Live WebSocket Feed",
                    "default_rooms": ["signals", "trades", "account"],
                }
            )
        )

        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
                action = msg.get("action")
                room = msg.get("room")

                if action == "subscribe" and room:
                    await ws_manager.subscribe(websocket, room)
                    await websocket.send_text(
                        json.dumps({"type": "subscribed", "room": room})
                    )
                elif action == "unsubscribe" and room:
                    await ws_manager.unsubscribe(websocket, room)
                    await websocket.send_text(
                        json.dumps({"type": "unsubscribed", "room": room})
                    )
                elif action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                else:
                    logger.debug("Received unhandled WebSocket client action: %s", action)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON format."})
                )

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("Unexpected WebSocket connection exception: %s", exc)
        await ws_manager.disconnect(websocket)


@router.websocket("/ws/market-data/{symbol}")
async def websocket_market_data_endpoint(websocket: WebSocket, symbol: str) -> None:
    """
    Dedicated WebSocket endpoint bound directly to real-time quotes for a symbol.
    """
    sym = symbol.upper()
    await ws_manager.connect(websocket)
    try:
        room_name = f"ticks:{sym}"
        await ws_manager.subscribe(websocket, room_name)

        await websocket.send_text(
            json.dumps(
                {
                    "type": "market_data_connected",
                    "symbol": sym,
                    "room": room_name,
                }
            )
        )

        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("Error in symbol market data WebSocket (%s): %s", sym, exc)
        await ws_manager.disconnect(websocket)
