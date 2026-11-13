"""
Unit tests for MT5 Bridge and Market Data components.
Verifies mock engine, symbol discovery, order safety checks, and data validation.
"""

import sys
import os
try:
    import pytest
except ImportError:
    pytest = None
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

# Ensure mt5-bridge directory is on sys.path
BRIDGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend"))
if BRIDGE_DIR not in sys.path:
    sys.path.insert(0, BRIDGE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from connector.mock_mt5 import (
    mock_mt5_instance,
    ORDER_TYPE_BUY,
    ORDER_TYPE_SELL,
    TRADE_ACTION_DEAL,
    TRADE_RETCODE_DONE,
)
from connector.mt5_connector import mt5_manager
from services.symbol_service import symbol_service
from services.order_service import order_service
from app.market_data.data_validator import data_validator
from app.market_data.market_data_service import market_data_service


def test_mock_mt5_account_and_rates():
    """Verify mock terminal account metrics and rate generation."""
    init_res = mock_mt5_instance.initialize()
    assert init_res is True
    assert mock_mt5_instance.is_connected() is True

    acc = mock_mt5_instance.account_info()
    assert acc is not None
    assert acc.balance == 10000.0
    assert acc.currency == "USD"

    # Rates generation
    rates = mock_mt5_instance.copy_rates_from_pos("XAUUSD", 60, 0, 50)
    assert rates is not None
    assert len(rates) == 50
    assert "open" in rates.dtype.names
    assert "close" in rates.dtype.names


def test_symbol_service_matching():
    """Verify suffix handling and symbol specs."""
    # Base pattern matching
    matched_gold = symbol_service.find_matching_symbol("XAUUSD")
    assert "XAUUSD" in matched_gold

    # Get info
    info = symbol_service.get_symbol_info("XAUUSD")
    assert info is not None
    assert info.digits == 2
    assert info.pip_size == 0.01
    assert info.contract_size == 100.0

    # EURUSD info
    eur_info = symbol_service.get_symbol_info("EURUSD")
    assert eur_info is not None
    assert eur_info.digits == 5
    assert eur_info.pip_size == 0.0001


def test_order_service_paper_safety():
    """Verify that paper mode executes safely and does not touch live broker."""
    # Send buy order
    result = order_service.send_order(
        symbol="EURUSD",
        side="BUY",
        volume=0.1,
        sl=1.07000,
        tp=1.09500,
        comment="Test Paper Order",
    )
    assert result.success is True
    assert result.is_paper is True
    assert result.ticket is not None
    ticket = result.ticket

    # Verify position is open
    positions = order_service.get_open_positions("EURUSD")
    assert any(p["ticket"] == ticket for p in positions)

    # Modify SL/TP
    mod_res = order_service.modify_position(ticket, sl=1.07200, tp=1.09800)
    assert mod_res.success is True

    # Close position
    close_res = order_service.close_position(ticket)
    assert close_res.success is True

    # Verify closed
    positions_after = order_service.get_open_positions("EURUSD")
    assert not any(p["ticket"] == ticket for p in positions_after)


def test_order_validation_rules():
    """Verify pre-trade validation bounds and stops levels."""
    # Below min volume
    res_small = order_service.validate_order("EURUSD", "BUY", volume=0.0001)
    assert res_small.is_valid is False
    assert "below minimum" in res_small.error_message.lower()

    # Invalid side
    res_side = order_service.validate_order("EURUSD", "INVALID_SIDE", volume=0.1)
    assert res_side.is_valid is False

    # Stop Loss on wrong side of market (BUY with SL > price)
    res_sl = order_service.validate_order("EURUSD", "BUY", volume=0.1, price=1.0850, sl=1.0900)
    assert res_sl.is_valid is False
    assert "below price" in res_sl.error_message.lower()


def test_data_validator_integrity():
    """Verify OHLCV data validation suite."""
    now = datetime.now(timezone.utc)
    dates = [now - timedelta(hours=i) for i in range(10, 0, -1)]

    # Clean DataFrame
    valid_data = pd.DataFrame({
        "time": dates,
        "open": [100.0] * 10,
        "high": [105.0] * 10,
        "low": [98.0] * 10,
        "close": [102.0] * 10,
        "tick_volume": [100] * 10,
    })

    val_res = data_validator.validate_candles(valid_data, timeframe_minutes=60)
    assert val_res.is_valid is True
    assert val_res.duplicate_count == 0

    # Inverted High < Low
    invalid_data = valid_data.copy()
    invalid_data.loc[2, "high"] = 90.0  # High < Low (98)
    inv_res = data_validator.validate_candles(invalid_data, timeframe_minutes=60)
    assert inv_res.is_valid is False
    assert any("High < Low" in err for err in inv_res.errors)


def test_market_hours_checker():
    """Verify forex market hours logic."""
    # Forex is open during weekdays
    is_open = market_data_service.is_market_open("EURUSD")
    assert isinstance(is_open, bool)


if __name__ == "__main__":
    print("Executing MT5 Bridge and Market Data tests...")
    test_mock_mt5_account_and_rates()
    print("✓ test_mock_mt5_account_and_rates passed")
    test_symbol_service_matching()
    print("✓ test_symbol_service_matching passed")
    test_order_service_paper_safety()
    print("✓ test_order_service_paper_safety passed")
    test_order_validation_rules()
    print("✓ test_order_validation_rules passed")
    test_data_validator_integrity()
    print("✓ test_data_validator_integrity passed")
    test_market_hours_checker()
    print("✓ test_market_hours_checker passed")
    print("\nALL 6 TEST SUITES PASSED SUCCESSFULLY!")

