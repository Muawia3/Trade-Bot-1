"""
Broker-Agnostic Symbol Discovery and Specification Service.
Handles dynamic suffix detection (e.g. XAUUSDm, XAUUSD.ecn, EURUSDc, EURUSD.a),
symbol property extraction, tick sizing, pip calculations, and availability verification.
"""

import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

# Import connector and mock components
try:
    from connector.mt5_connector import mt5_manager, mt5, _MT5_AVAILABLE
    from connector.mock_mt5 import mock_mt5_instance
except ImportError:
    from mt5_bridge.connector.mt5_connector import mt5_manager, mt5, _MT5_AVAILABLE
    from mt5_bridge.connector.mock_mt5 import mock_mt5_instance

logger = logging.getLogger("mt5_bridge.symbol_service")


@dataclass
class SymbolInfo:
    """Standardized instrument specifications across brokers."""
    name: str
    base_currency: str
    quote_currency: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level: int
    freeze_level: int
    spread: int
    trade_mode: int
    is_visible: bool
    is_tradable: bool
    pip_size: float
    pip_value: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        return asdict(self)


class SymbolService:
    """
    Broker-agnostic discovery and validation service for trading symbols.
    Dynamically identifies broker symbol naming variations without hardcoding suffixes.
    """

    def __init__(self):
        self._cached_symbols: Dict[str, SymbolInfo] = {}
        self._name_mapping: Dict[str, str] = {}  # base -> broker specific symbol

    def _normalize_name(self, raw_symbol: str) -> str:
        """Strip non-alphanumeric characters and uppercase."""
        return re.sub(r"[^A-Za-z0-9]", "", raw_symbol).upper()

    def discover_symbols(self) -> List[str]:
        """
        Scan MT5 terminal for all available market symbols.
        Returns a list of all active symbol names.
        """
        symbols: List[str] = []

        if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
            mock_symbols = mock_mt5_instance.symbols_get()
            symbols = [s.name for s in mock_symbols]
        else:
            try:
                native_symbols = mt5.symbols_get()
                if native_symbols:
                    symbols = [s.name for s in native_symbols]
            except Exception as e:
                logger.error("Error reading symbols from MT5: %s", e)
                mock_symbols = mock_mt5_instance.symbols_get()
                symbols = [s.name for s in mock_symbols]

        logger.info("Discovered %d market symbols.", len(symbols))
        return symbols

    def find_matching_symbol(self, base_pattern: str) -> Optional[str]:
        """
        Dynamically locate the broker's exact symbol name for a given canonical instrument.
        Handles variations like:
          - XAUUSD -> XAUUSD, XAUUSDm, XAUUSD.ecn, XAUUSD_i, GOLD, XAUUSDc
          - EURUSD -> EURUSD, EURUSD+, EURUSDm, EURUSD.a, EURUSD.pro
        """
        clean_target = self._normalize_name(base_pattern)
        if clean_target in self._name_mapping:
            return self._name_mapping[clean_target]

        available = self.discover_symbols()
        if not available:
            # Fallback to base pattern itself if none discovered
            return base_pattern

        # 1. Exact match
        for s in available:
            if s.upper() == base_pattern.upper():
                self._name_mapping[clean_target] = s
                return s

        # 2. Normalized match (ignoring dots, dashes, underscores)
        for s in available:
            if self._normalize_name(s) == clean_target:
                self._name_mapping[clean_target] = s
                return s

        # 3. Target starts with base pattern (e.g. XAUUSDm, EURUSD.a)
        for s in available:
            norm_s = self._normalize_name(s)
            if norm_s.startswith(clean_target) and len(norm_s) <= len(clean_target) + 4:
                self._name_mapping[clean_target] = s
                return s

        # 4. Synonym handling for Gold (GOLD -> XAUUSD, XAUUSD -> GOLD)
        if clean_target in ("XAUUSD", "GOLD"):
            for s in available:
                norm_s = self._normalize_name(s)
                if "XAUUSD" in norm_s or "GOLD" in norm_s:
                    self._name_mapping[clean_target] = s
                    return s

        # 5. Substring matching as last resort
        for s in available:
            if clean_target in self._normalize_name(s):
                self._name_mapping[clean_target] = s
                return s

        logger.warning("No broker symbol matched base pattern '%s'. Defaulting to base.", base_pattern)
        return base_pattern

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        Fetch full technical specification of symbol.
        Computes accurate point, tick value, tick size, pip size, and trading limits.
        """
        # Resolve broker-specific symbol name first
        resolved_name = self.find_matching_symbol(symbol) or symbol

        raw_info = None
        if mt5_manager.is_mock_mode or not _MT5_AVAILABLE or mt5 is None:
            raw_info = mock_mt5_instance.symbol_info(resolved_name)
        else:
            try:
                # Ensure symbol is selected in Market Watch
                mt5.symbol_select(resolved_name, True)
                raw_info = mt5.symbol_info(resolved_name)
            except Exception as e:
                logger.error("Error fetching symbol info for %s: %s", resolved_name, e)
                raw_info = mock_mt5_instance.symbol_info(resolved_name)

        if raw_info is None:
            logger.error("Symbol '%s' not found in MT5 or mock engine.", resolved_name)
            return None

        # Calculate standard pip size (0.0001 for 4/5 digit forex, 0.01 for 2/3 digit pairs & gold)
        digits = int(getattr(raw_info, "digits", 5))
        point = float(getattr(raw_info, "point", 0.00001))
        pip_size = 10 * point if digits in (3, 5) else point

        # Calculate pip value based on tick size and tick value
        tick_size = float(getattr(raw_info, "trade_tick_size", point))
        tick_value = float(getattr(raw_info, "trade_tick_value", 1.0))
        contract_size = float(getattr(raw_info, "trade_contract_size", 100000.0))

        if tick_size > 0:
            pip_value = (pip_size / tick_size) * tick_value
        else:
            pip_value = tick_value

        trade_mode = int(getattr(raw_info, "trade_mode", 4))
        # trade_mode == 4 is SYMBOL_TRADE_MODE_FULL
        is_tradable = trade_mode == 4

        info_obj = SymbolInfo(
            name=getattr(raw_info, "name", resolved_name),
            base_currency=getattr(raw_info, "currency_base", resolved_name[:3]),
            quote_currency=getattr(raw_info, "currency_profit", "USD"),
            digits=digits,
            point=point,
            tick_size=tick_size,
            tick_value=tick_value,
            contract_size=contract_size,
            volume_min=float(getattr(raw_info, "volume_min", 0.01)),
            volume_max=float(getattr(raw_info, "volume_max", 100.0)),
            volume_step=float(getattr(raw_info, "volume_step", 0.01)),
            stops_level=int(getattr(raw_info, "trade_stops_level", 0)),
            freeze_level=int(getattr(raw_info, "trade_freeze_level", 0)),
            spread=int(getattr(raw_info, "spread", 0)),
            trade_mode=trade_mode,
            is_visible=bool(getattr(raw_info, "visible", True)),
            is_tradable=is_tradable,
            pip_size=pip_size,
            pip_value=pip_value,
        )

        self._cached_symbols[resolved_name] = info_obj
        return info_obj

    def validate_symbol(self, symbol: str) -> bool:
        """
        Verify if symbol exists and is tradable.
        """
        info = self.get_symbol_info(symbol)
        if not info:
            return False
        return info.is_tradable and info.is_visible


# Global SymbolService instance
symbol_service = SymbolService()
