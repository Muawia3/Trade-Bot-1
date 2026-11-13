"""
Strategies module for algorithmic Forex & Gold trading.
"""

from app.strategies.base import BaseStrategy, StrategyResult
from app.strategies.bollinger_bands import BollingerBandsStrategy
from app.strategies.ema_crossover import EMACrossoverStrategy
from app.strategies.macd_confirmation import MACDConfirmationStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.multi_indicator import MultiIndicatorStrategy
from app.strategies.rsi_reversal import RSIReversalStrategy
from app.strategies.strategy_manager import StrategyManager
from app.strategies.trend_following import TrendFollowingStrategy

__all__ = [
    "BaseStrategy",
    "StrategyResult",
    "TrendFollowingStrategy",
    "EMACrossoverStrategy",
    "RSIReversalStrategy",
    "MACDConfirmationStrategy",
    "BollingerBandsStrategy",
    "MomentumStrategy",
    "MultiIndicatorStrategy",
    "StrategyManager",
]
