"""MT5 Bridge Connector Package."""

from .mt5_connector import MT5Manager, mt5_manager
from .mock_mt5 import (
    MockMT5Client,
    mock_mt5_instance,
    MockAccountInfo,
    MockSymbolInfo,
    MockTick,
    MockOrderSendResult,
)

__all__ = [
    "MT5Manager",
    "mt5_manager",
    "MockMT5Client",
    "mock_mt5_instance",
    "MockAccountInfo",
    "MockSymbolInfo",
    "MockTick",
    "MockOrderSendResult",
]
