"""
Core MetaTrader 5 Connection Manager.
Wraps the MetaTrader5 Python API with connection pooling, exponential backoff,
robust error recovery, and transparent fallback to Mock mode when MT5 is unavailable.
"""

import sys
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List, Union
from datetime import datetime, timezone

# Import configuration
try:
    from config.bridge_config import get_bridge_config, BridgeConfig
except ImportError:
    from mt5_bridge.config.bridge_config import get_bridge_config, BridgeConfig

# Try importing official MetaTrader5 package
_MT5_AVAILABLE = False
mt5 = None

if sys.platform.startswith("win"):
    try:
        import MetaTrader5 as mt5_module
        mt5 = mt5_module
        _MT5_AVAILABLE = True
    except ImportError:
        _MT5_AVAILABLE = False

from .mock_mt5 import (
    mock_mt5_instance,
    MockAccountInfo,
    MockSymbolInfo,
    MockTick,
    MockOrderSendResult,
    TRADE_RETCODE_DONE,
)

logger = logging.getLogger("mt5_bridge.connector")


class MT5Manager:
    """
    Thread-safe MetaTrader 5 Connection and API lifecycle manager.
    Handles initialization, health checks, reconnection with exponential backoff,
    and fallback to mock execution when MT5 is not present.
    """

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config: BridgeConfig = config or get_bridge_config()
        self._connected: bool = False
        self._mock_mode: bool = False
        self._lock = asyncio.Lock()
        self._reconnect_attempts: int = 0
        self._last_connected_time: Optional[datetime] = None

        # Check if forced mock or MT5 unavailable
        if self.config.MOCK_MODE or not _MT5_AVAILABLE:
            self._mock_mode = True
            logger.info("MT5Manager initialized in MOCK MODE (MT5 available: %s, Mock configured: %s)", _MT5_AVAILABLE, self.config.MOCK_MODE)
        else:
            logger.info("MT5Manager initialized for Native MetaTrader 5 on Windows.")

    @property
    def is_mock_mode(self) -> bool:
        """Return True if running in simulated mock mode."""
        return self._mock_mode

    @property
    def is_connected(self) -> bool:
        """Check whether terminal connection is currently alive."""
        if self._mock_mode:
            return mock_mt5_instance.is_connected()
        if not _MT5_AVAILABLE or mt5 is None:
            return False
        return self._connected

    def initialize_sync(
        self,
        path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """
        Synchronous initialization of the MT5 connection.
        """
        path = path or self.config.MT5_PATH
        login = login if login is not None else self.config.MT5_LOGIN
        password = password or self.config.MT5_PASSWORD
        server = server or self.config.MT5_SERVER
        timeout = timeout or self.config.MT5_TIMEOUT

        if self._mock_mode:
            logger.info("Initializing Mock MT5 engine (login=%s, server=%s)...", login, server)
            self._connected = mock_mt5_instance.initialize(
                path=path,
                login=login,
                password=password,
                server=server,
                timeout=timeout,
            )
            if self._connected:
                self._last_connected_time = datetime.now(timezone.utc)
            return self._connected

        # Real MT5 Terminal initialization
        logger.info("Connecting to MT5 terminal at '%s' (server='%s', login=%s)...", path, server, login)
        try:
            init_kwargs: Dict[str, Any] = {"timeout": timeout}
            if path:
                init_kwargs["path"] = path
            if login:
                init_kwargs["login"] = int(login)
            if password:
                init_kwargs["password"] = password
            if server:
                init_kwargs["server"] = server

            res = mt5.initialize(**init_kwargs)
            if not res:
                err_code, err_msg = mt5.last_error()
                logger.error("MT5 initialization failed! Code: %s, Message: %s", err_code, err_msg)
                self._connected = False
                return False

            # Verify terminal account status
            acc = mt5.account_info()
            if acc is None:
                err_code, err_msg = mt5.last_error()
                logger.error("MT5 terminal started but account_info() is None! Code: %s, Message: %s", err_code, err_msg)
                self._connected = False
                return False

            self._connected = True
            self._reconnect_attempts = 0
            self._last_connected_time = datetime.now(timezone.utc)
            logger.info("MT5 successfully connected to server '%s' (Account: %s, Currency: %s)", acc.server, acc.login, acc.currency)
            return True

        except Exception as ex:
            logger.exception("Unexpected error during MT5 initialization: %s. Falling back to mock.", ex)
            self._mock_mode = True
            self._connected = mock_mt5_instance.initialize(path=path, login=login, password=password, server=server)
            return self._connected

    async def initialize(
        self,
        path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """Asynchronous initialization wrapper."""
        async with self._lock:
            return await asyncio.to_thread(
                self.initialize_sync, path, login, password, server, timeout
            )

    def shutdown_sync(self) -> None:
        """Synchronous terminal shutdown."""
        if self._mock_mode:
            mock_mt5_instance.shutdown()
            self._connected = False
            logger.info("Mock MT5 engine shut down.")
            return

        if _MT5_AVAILABLE and mt5 is not None:
            try:
                mt5.shutdown()
                logger.info("MT5 connection shut down cleanly.")
            except Exception as e:
                logger.warning("Error during MT5 shutdown: %s", e)
            finally:
                self._connected = False

    async def shutdown(self) -> None:
        """Asynchronous terminal shutdown."""
        async with self._lock:
            await asyncio.to_thread(self.shutdown_sync)

    async def reconnect(self) -> bool:
        """
        Attempt reconnection using exponential backoff strategy.
        """
        async with self._lock:
            logger.warning("Initiating MT5 reconnect procedure...")
            self.shutdown_sync()

            max_attempts = self.config.MAX_RECONNECT_ATTEMPTS
            backoff = self.config.INITIAL_BACKOFF_SECONDS
            multiplier = self.config.BACKOFF_MULTIPLIER
            max_backoff = self.config.MAX_BACKOFF_SECONDS

            for attempt in range(1, max_attempts + 1):
                self._reconnect_attempts = attempt
                logger.info("MT5 reconnect attempt %d of %d (delay: %.1fs)...", attempt, max_attempts, backoff)
                await asyncio.sleep(backoff)

                success = await asyncio.to_thread(self.initialize_sync)
                if success:
                    logger.info("MT5 reconnection successful on attempt %d!", attempt)
                    return True

                backoff = min(backoff * multiplier, max_backoff)

            logger.error("MT5 reconnection failed after %d attempts. Activating mock mode.", max_attempts)
            self._mock_mode = True
            return mock_mt5_instance.initialize()

    def get_account_info_sync(self) -> Dict[str, Any]:
        """
        Retrieve standardized account metrics.
        Returns dict with balance, equity, margin, free_margin, currency, leverage, server, name, company.
        """
        if self._mock_mode:
            acc = mock_mt5_instance.account_info()
            if not acc:
                return {}
            return {
                "login": acc.login,
                "balance": float(acc.balance),
                "equity": float(acc.equity),
                "margin": float(acc.margin),
                "free_margin": float(acc.margin_free),
                "margin_level": float(acc.margin_level),
                "profit": float(acc.profit),
                "currency": acc.currency,
                "leverage": acc.leverage,
                "server": acc.server,
                "name": acc.name,
                "company": acc.company,
                "trade_allowed": acc.trade_allowed,
                "is_mock": True,
            }

        if not self._connected or mt5 is None:
            return {}

        acc = mt5.account_info()
        if acc is None:
            err = mt5.last_error()
            logger.error("Failed to fetch MT5 account info: %s", err)
            return {}

        return {
            "login": acc.login,
            "balance": float(acc.balance),
            "equity": float(acc.equity),
            "margin": float(acc.margin),
            "free_margin": float(acc.margin_free),
            "margin_level": float(acc.margin_level) if hasattr(acc, "margin_level") else 0.0,
            "profit": float(acc.profit),
            "currency": acc.currency,
            "leverage": acc.leverage,
            "server": acc.server,
            "name": acc.name,
            "company": acc.company,
            "trade_allowed": bool(acc.trade_allowed),
            "is_mock": False,
        }

    async def get_account_info(self) -> Dict[str, Any]:
        """Asynchronous wrapper for get_account_info."""
        return await asyncio.to_thread(self.get_account_info_sync)

    def get_last_error(self) -> Tuple[int, str]:
        """Return last error from MT5 or mock engine."""
        if self._mock_mode:
            return mock_mt5_instance.last_error()
        if _MT5_AVAILABLE and mt5 is not None:
            return mt5.last_error()
        return (-1, "MT5 package not loaded")


# Global connector instance
mt5_manager = MT5Manager()
