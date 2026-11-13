"""
Strategy Manager.
Central registry and lifecycle manager for all trading strategies across symbols.
"""

from typing import Any, Dict, List, Optional
import pandas as pd

from app.core.constants import TARGET_INSTRUMENTS, TimeFrame
from app.core.logging_config import get_logger
from app.strategies.base import BaseStrategy, StrategyResult
from app.strategies.bollinger_bands import BollingerBandsStrategy
from app.strategies.ema_crossover import EMACrossoverStrategy
from app.strategies.macd_confirmation import MACDConfirmationStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.multi_indicator import MultiIndicatorStrategy
from app.strategies.rsi_reversal import RSIReversalStrategy
from app.strategies.trend_following import TrendFollowingStrategy

logger = get_logger("strategies.manager")


class StrategyManager:
    """
    Manages active trading strategies, handles dynamic registrations,
    enables/disables strategies per symbol, and evaluates market data.
    """

    def __init__(self):
        # Key: (strategy_name, symbol) -> BaseStrategy
        self._strategies: Dict[str, BaseStrategy] = {}

    def _make_key(self, name: str, symbol: str) -> str:
        return f"{name.lower()}::{symbol.upper()}"

    def register_strategy(self, strategy: BaseStrategy) -> None:
        """Registers a strategy instance."""
        key = self._make_key(strategy.name, strategy.symbol)
        self._strategies[key] = strategy
        logger.info("Registered strategy %s for symbol %s (enabled=%s)", strategy.name, strategy.symbol, strategy.enabled)

    def unregister_strategy(self, name: str, symbol: str) -> bool:
        """Removes a strategy from registry."""
        key = self._make_key(name, symbol)
        if key in self._strategies:
            del self._strategies[key]
            logger.info("Unregistered strategy %s for %s", name, symbol)
            return True
        return False

    def get_strategy(self, name: str, symbol: str) -> Optional[BaseStrategy]:
        """Retrieves a specific strategy by name and symbol."""
        key = self._make_key(name, symbol)
        return self._strategies.get(key)

    def get_strategies_for_symbol(self, symbol: str, only_enabled: bool = True) -> List[BaseStrategy]:
        """Returns all strategies registered for a specific symbol."""
        sym_upper = symbol.upper()
        matching = [
            s for s in self._strategies.values()
            if s.symbol == sym_upper and (not only_enabled or s.enabled)
        ]
        return matching

    def get_all_strategies(self, only_enabled: bool = False) -> List[BaseStrategy]:
        """Returns all registered strategies."""
        if only_enabled:
            return [s for s in self._strategies.values() if s.enabled]
        return list(self._strategies.values())

    def enable_strategy(self, name: str, symbol: str) -> bool:
        """Enables a strategy."""
        strat = self.get_strategy(name, symbol)
        if strat:
            strat.enabled = True
            logger.info("Enabled strategy %s for %s", name, symbol)
            return True
        return False

    def disable_strategy(self, name: str, symbol: str) -> bool:
        """Disables a strategy."""
        strat = self.get_strategy(name, symbol)
        if strat:
            strat.enabled = False
            logger.info("Disabled strategy %s for %s", name, symbol)
            return True
        return False

    def evaluate_all(
        self,
        symbol: str,
        market_data: pd.DataFrame,
        symbol_info: Optional[Dict[str, Any]] = None,
        only_enabled: bool = True,
    ) -> List[StrategyResult]:
        """
        Runs analysis across all registered strategies for a given symbol.

        Args:
            symbol: Target symbol (e.g. 'EURUSD', 'XAUUSD').
            market_data: DataFrame with OHLCV data.
            symbol_info: Broker symbol specifications.
            only_enabled: If True, only evaluate enabled strategies.

        Returns:
            List of StrategyResult objects from all evaluated strategies.
        """
        strategies = self.get_strategies_for_symbol(symbol, only_enabled=only_enabled)
        results: List[StrategyResult] = []

        if not strategies:
            logger.debug("No strategies registered or enabled for symbol %s", symbol)
            return results

        for strat in strategies:
            try:
                res = strat.analyze(market_data, symbol_info=symbol_info)
                results.append(res)
            except Exception as e:
                logger.error(
                    "Error executing strategy %s on %s: %s",
                    strat.name,
                    symbol,
                    str(e),
                    exc_info=True,
                )

        return results

    def load_default_strategies(self, symbols: Optional[List[str]] = None) -> None:
        """
        Instantiates and registers the default suite of production strategies
        for given symbols (defaults to EURUSD and XAUUSD).
        """
        target_symbols = symbols or ["EURUSD", "XAUUSD"]

        for sym in target_symbols:
            # 1. Trend Following (Primary on H1)
            self.register_strategy(TrendFollowingStrategy(symbol=sym, timeframe=TimeFrame.H1))
            # 2. Multi-Indicator Consensus (Robust on H1)
            self.register_strategy(MultiIndicatorStrategy(symbol=sym, timeframe=TimeFrame.H1))
            # 3. EMA Crossover (Fast trend shifts on M15/H1)
            self.register_strategy(EMACrossoverStrategy(symbol=sym, timeframe=TimeFrame.H1))
            # 4. MACD Confirmation (Momentum expansions on H1)
            self.register_strategy(MACDConfirmationStrategy(symbol=sym, timeframe=TimeFrame.H1))
            # 5. RSI Reversal (Mean-reversion pullbacks on M15)
            self.register_strategy(RSIReversalStrategy(symbol=sym, timeframe=TimeFrame.M15))
            # 6. Bollinger Bands (Range/mean reversion on M30)
            self.register_strategy(BollingerBandsStrategy(symbol=sym, timeframe=TimeFrame.M30))

        logger.info(
            "Loaded default strategies suite for %d symbols (total registered: %d)",
            len(target_symbols),
            len(self._strategies),
        )

    def load_from_configs(self, configs: List[Dict[str, Any]]) -> None:
        """
        Dynamically configures strategies from database records or dictionary configs.
        """
        strategy_class_map = {
            "trendfollowing": TrendFollowingStrategy,
            "emacrossover": EMACrossoverStrategy,
            "rsireversal": RSIReversalStrategy,
            "macdconfirmation": MACDConfirmationStrategy,
            "bollingerbands": BollingerBandsStrategy,
            "momentumstrategy": MomentumStrategy,
            "multiindicatorconsensus": MultiIndicatorStrategy,
        }

        for cfg in configs:
            name = cfg.get("name", "").strip()
            symbol = cfg.get("symbol", "EURUSD").strip().upper()
            timeframe = cfg.get("timeframe", TimeFrame.H1)
            enabled = cfg.get("enabled", True)
            params = cfg.get("parameters", {})

            clean_name = name.lower().replace(" ", "").replace("_", "")
            cls = strategy_class_map.get(clean_name)
            if not cls:
                logger.warning("Unknown strategy class '%s' in configuration", name)
                continue

            instance = cls(symbol=symbol, timeframe=timeframe, parameters=params)
            instance.enabled = enabled
            self.register_strategy(instance)
