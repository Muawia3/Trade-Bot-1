"""
MT5 Bridge Client for Backend Services.
Provides async HTTP client interface to the MT5 Bridge microservice (running on port 8001).
"""

import os
import logging
from typing import Dict, Any, Optional, List
import httpx

from app.core.config import get_settings

logger = logging.getLogger("backend.mt5.client")


class MT5BridgeClient:
    """Async client communicating with the MT5 Bridge microservice."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("MT5_BRIDGE_URL", "http://localhost:8001")).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=15.0)
        return self._client

    async def get_health(self) -> Dict[str, Any]:
        """Check MT5 Bridge health status."""
        client = await self._get_client()
        try:
            r = await client.get("/health")
            return r.json()
        except Exception as e:
            logger.error("Failed to connect to MT5 bridge health endpoint: %s", e)
            return {"status": "error", "mt5_connected": False, "error": str(e)}

    async def get_account(self) -> Dict[str, Any]:
        """Fetch account metrics from MT5."""
        client = await self._get_client()
        r = await client.get("/account")
        r.raise_for_status()
        return r.json()

    async def get_symbols(self) -> List[str]:
        """Fetch discovered symbols."""
        client = await self._get_client()
        r = await client.get("/symbols")
        r.raise_for_status()
        return r.json().get("symbols", [])

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch technical specifications for a symbol."""
        client = await self._get_client()
        r = await client.get(f"/symbols/{symbol}")
        r.raise_for_status()
        return r.json()

    async def place_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit order to MT5 Bridge."""
        client = await self._get_client()
        r = await client.post("/orders", json=order_data)
        r.raise_for_status()
        return r.json()

    async def modify_position(self, ticket: int, sl: float, tp: float) -> Dict[str, Any]:
        """Modify position SL/TP."""
        client = await self._get_client()
        r = await client.put(f"/orders/{ticket}", json={"sl": sl, "tp": tp})
        r.raise_for_status()
        return r.json()

    async def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict[str, Any]:
        """Close open position."""
        client = await self._get_client()
        params = {"volume": volume} if volume else {}
        r = await client.delete(f"/orders/{ticket}", params=params)
        r.raise_for_status()
        return r.json()

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open positions."""
        client = await self._get_client()
        params = {"symbol": symbol} if symbol else {}
        r = await client.get("/positions", params=params)
        r.raise_for_status()
        return r.json().get("positions", [])

    async def get_history(self) -> List[Dict[str, Any]]:
        """Get trade history."""
        client = await self._get_client()
        r = await client.get("/history")
        r.raise_for_status()
        return r.json().get("trades", [])

    async def close(self):
        """Close client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton instance
mt5_bridge_client = MT5BridgeClient()
