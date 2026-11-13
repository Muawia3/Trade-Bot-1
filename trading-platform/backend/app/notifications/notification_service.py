"""
Notification Service.

Dispatches real-time alerts across channels (WebSockets to frontend UI, Webhooks,
Email) for new signals, trade executions, risk limit breaches, and system status events.
Maintains an in-memory audit log of recent notifications for UI consumption.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger("notifications.service")


class NotificationType(str, Enum):
    SIGNAL = "signal"
    TRADE_OPEN = "trade_open"
    TRADE_CLOSE = "trade_close"
    TRADE_MODIFIED = "trade_modified"
    RISK_ALERT = "risk_alert"
    SYSTEM_ALERT = "system_alert"


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Notification:
    """Notification message container."""

    id: str
    type: NotificationType
    severity: NotificationSeverity
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_read: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "is_read": self.is_read,
        }


class NotificationService:
    """
    Central notification dispatcher.
    Coordinates alerting across WebSocket, webhooks, and local audit storage.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        max_history_size: int = 500,
    ) -> None:
        self.settings = get_settings()
        self.webhook_url = webhook_url
        self.max_history_size = max_history_size
        self._history: List[Notification] = []
        self._listeners: List[Callable[[Notification], None]] = []

        logger.info("NotificationService initialized. History limit: %d", max_history_size)

    # -------------------------------------------------------------------------
    # Core Dispatcher
    # -------------------------------------------------------------------------
    def dispatch(
        self,
        notif_type: NotificationType,
        severity: NotificationSeverity,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Create, store, and dispatch a notification across all channels."""
        notif = Notification(
            id=str(uuid.uuid4()),
            type=notif_type,
            severity=severity,
            title=title,
            message=message,
            data=data or {},
        )

        # Append to bounded history
        self._history.insert(0, notif)
        if len(self._history) > self.max_history_size:
            self._history = self._history[: self.max_history_size]

        # Log according to severity
        log_msg = f"[{notif.type.value.upper()}] {notif.title} - {notif.message}"
        if severity == NotificationSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == NotificationSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Notify internal callbacks
        for listener in self._listeners:
            try:
                listener(notif)
            except Exception as e:
                logger.error("Notification listener error: %s", e)

        # Broadcast via WebSocket & Webhook asynchronously
        self._broadcast(notif)

        return notif

    def _broadcast(self, notif: Notification) -> None:
        """Send notification over WebSocket and Webhook."""
        payload = notif.to_dict()

        # Try WebSocket broadcast via ws_manager
        try:
            from app.websocket.manager import ws_manager
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws_manager.broadcast_to_room("notifications", {"type": "notification", "data": payload}))
                if notif.type == NotificationType.SIGNAL:
                    loop.create_task(ws_manager.broadcast_signal(payload))
                elif notif.type in (NotificationType.TRADE_OPEN, NotificationType.TRADE_CLOSE, NotificationType.TRADE_MODIFIED):
                    loop.create_task(ws_manager.broadcast_trade_update(payload))
            except RuntimeError:
                # If called outside an active event loop (e.g. sync script or test), run safe background dispatch
                pass
        except ImportError:
            pass

        # Push to external Webhook if configured
        if self.webhook_url:
            self._push_webhook_async(payload)

    def _push_webhook_async(self, payload: Dict[str, Any]) -> None:
        """Send asynchronous HTTP POST request to configured webhook URL."""
        async def _send():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(self.webhook_url, json=payload)
            except Exception as ex:
                logger.warning("Failed to deliver webhook notification: %s", ex)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send())
        except RuntimeError:
            pass

    # -------------------------------------------------------------------------
    # Convenience Notification Methods
    # -------------------------------------------------------------------------
    def notify_signal(self, signal: Any) -> Notification:
        """Emit notification for a newly generated trading signal."""
        sym = getattr(signal, "symbol", "") or (signal.get("symbol", "") if isinstance(signal, dict) else "")
        raw_sig = getattr(signal, "signal_type", None) or getattr(signal, "signal", None) or (signal.get("signal_type", signal.get("signal", "")) if isinstance(signal, dict) else "")
        sig_type = raw_sig.value if hasattr(raw_sig, "value") else str(raw_sig)
        strat = getattr(signal, "strategy_name", "") or (signal.get("strategy_name", "") if isinstance(signal, dict) else "")
        entry_raw = getattr(signal, "entry_price", None) or (signal.get("entry_price") if isinstance(signal, dict) else None)
        entry = float(entry_raw) if entry_raw is not None else 0.0
        conf = getattr(signal, "confidence", 1.0) or (signal.get("confidence", 1.0) if isinstance(signal, dict) else 1.0)

        title = f"New Signal: {sym} {sig_type}"
        msg = f"Strategy '{strat}' generated {sig_type} for {sym} @ {entry:.5f} (confidence: {conf:.0%})"

        data = signal if isinstance(signal, dict) else (signal.__dict__ if hasattr(signal, "__dict__") else {})
        return self.dispatch(
            notif_type=NotificationType.SIGNAL,
            severity=NotificationSeverity.INFO,
            title=title,
            message=msg,
            data=data,
        )

    def notify_trade_opened(self, trade_result: Any) -> Notification:
        """Emit notification when a trade order is executed."""
        sym = getattr(trade_result, "symbol", "")
        side = getattr(trade_result, "side", "")
        vol = getattr(trade_result, "volume", 0.0)
        price = getattr(trade_result, "price", 0.0)
        mode = getattr(trade_result, "trading_mode", "PAPER")

        title = f"Trade Opened ({mode}): {sym} {side} {vol:.2f} lots"
        msg = f"Filled {side} {vol:.2f} lots {sym} @ {price:.5f} [{mode} mode]."

        data = trade_result.to_dict() if hasattr(trade_result, "to_dict") else {}
        return self.dispatch(
            notif_type=NotificationType.TRADE_OPEN,
            severity=NotificationSeverity.INFO,
            title=title,
            message=msg,
            data=data,
        )

    def notify_trade_closed(self, trade_result: Any) -> Notification:
        """Emit notification when a position is closed."""
        sym = getattr(trade_result, "symbol", "")
        pnl = getattr(trade_result, "realized_pnl", 0.0)
        price = getattr(trade_result, "price", 0.0)
        reason = getattr(trade_result, "message", "Position closed")

        severity = NotificationSeverity.INFO if pnl >= 0 else NotificationSeverity.WARNING
        pnl_symbol = "+" if pnl >= 0 else ""
        title = f"Trade Closed: {sym} ({pnl_symbol}${pnl:.2f})"
        msg = f"Closed {sym} @ {price:.5f}. Realized PnL: {pnl_symbol}${pnl:.2f}. ({reason})"

        data = trade_result.to_dict() if hasattr(trade_result, "to_dict") else {}
        return self.dispatch(
            notif_type=NotificationType.TRADE_CLOSE,
            severity=severity,
            title=title,
            message=msg,
            data=data,
        )

    def notify_trade_modified(self, position: Any) -> Notification:
        """Emit notification when an existing position's SL/TP is adjusted."""
        sym = getattr(position, "symbol", "")
        sl = getattr(position, "sl", None)
        tp = getattr(position, "tp", None)

        title = f"Position Modified: {sym}"
        msg = f"Updated orders for {sym}: SL={sl}, TP={tp}"
        data = position.to_dict() if hasattr(position, "to_dict") else {}

        return self.dispatch(
            notif_type=NotificationType.TRADE_MODIFIED,
            severity=NotificationSeverity.INFO,
            title=title,
            message=msg,
            data=data,
        )

    def notify_risk_alert(
        self,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.WARNING,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Emit an alert for risk parameters, drawdown thresholds, or high portfolio heat."""
        return self.dispatch(
            notif_type=NotificationType.RISK_ALERT,
            severity=severity,
            title=title,
            message=message,
            data=data,
        )

    def notify_system_alert(
        self,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Emit alert for system events (MT5 disconnected, market hours, database status)."""
        return self.dispatch(
            notif_type=NotificationType.SYSTEM_ALERT,
            severity=severity,
            title=title,
            message=message,
            data=data,
        )

    # -------------------------------------------------------------------------
    # History Management
    # -------------------------------------------------------------------------
    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notif_type: Optional[NotificationType] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve historical notifications with optional filtering and pagination."""
        items = self._history
        if unread_only:
            items = [n for n in items if not n.is_read]
        if notif_type:
            items = [n for n in items if n.type == notif_type]

        sliced = items[offset : offset + limit]
        return [n.to_dict() for n in sliced]

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark a single notification as read."""
        for n in self._history:
            if n.id == notification_id:
                n.is_read = True
                return True
        return False

    def mark_all_as_read(self) -> None:
        """Mark all buffered notifications as read."""
        for n in self._history:
            n.is_read = True

    def register_listener(self, callback: Callable[[Notification], None]) -> None:
        """Register a callback for all new notifications."""
        self._listeners.append(callback)


# Application-level singleton
_global_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Return the application singleton NotificationService."""
    global _global_notification_service
    if _global_notification_service is None:
        _global_notification_service = NotificationService()
    return _global_notification_service
