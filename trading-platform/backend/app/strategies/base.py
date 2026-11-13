"""
Base strategy module defining the contract and data structures for all trading strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd

from app.core.constants import DEFAULT_STOP_LOSS_PIPS, DEFAULT_TAKE_PROFIT_PIPS, SignalType, TimeFrame
from app.core.logging_config import get_logger

logger = get_logger("strategies.base")


@dataclass
class StrategyResult:
    """Standardized result returned by any strategy analysis."""
    strategy_name: str
    symbol: str
    timeframe: str
    signal: SignalType
    confidence: float  # Scale: 0.0 to 1.0
    reasoning: str
    indicators_used: Dict[str, Any] = field(default_factory=dict)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_actionable(self) -> bool:
        """Returns True if the result represents an active BUY or SELL signal."""
        return self.signal in (SignalType.BUY, SignalType.SELL)


class BaseStrategy(ABC):
    """
    Abstract Base Class for all quantitative and rule-based trading strategies.
    
    IMPORTANT: No strategy makes claims of guaranteed profitability.
    All strategies must provide transparent reasoning and full indicator justification.
    """

    def __init__(
        self,
        name: str,
        symbol: str = "EURUSD",
        timeframe: Union[TimeFrame, str] = TimeFrame.H1,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.symbol = symbol.upper()
        self.timeframe = timeframe.name if isinstance(timeframe, TimeFrame) else str(timeframe)
        self.parameters = parameters or {}
        self.enabled: bool = True

    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol_info: Optional[Dict[str, Any]] = None) -> StrategyResult:
        """
        Analyzes candle data and indicators, evaluating entry/exit rules.

        Args:
            df: DataFrame containing price and indicator columns.
            symbol_info: Broker specification for the symbol (point size, digits, etc.).

        Returns:
            StrategyResult with signal direction, confidence, reasoning, and suggested SL/TP.
        """
        pass

    def validate_signal(self, result: StrategyResult, risk_params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validates the generated signal against basic structural sanity checks.
        Detailed account-level checks are handled by the RiskManager.
        """
        if not self.enabled:
            logger.info("Strategy %s is disabled; rejecting signal", self.name)
            return False

        if not result.is_actionable:
            return True

        # Confidence sanity check
        if result.confidence <= 0.0 or result.confidence > 1.0:
            logger.warning("Invalid confidence level: %f", result.confidence)
            return False

        # Entry price must be positive
        if result.entry_price is None or result.entry_price <= 0:
            logger.warning("Invalid entry price in signal: %s", str(result.entry_price))
            return False

        # Stop loss validation: BUY must have SL < entry, SELL must have SL > entry
        if result.stop_loss is not None:
            if result.signal == SignalType.BUY and result.stop_loss >= result.entry_price:
                logger.warning("Invalid SL for BUY (%f >= %f)", result.stop_loss, result.entry_price)
                return False
            if result.signal == SignalType.SELL and result.stop_loss <= result.entry_price:
                logger.warning("Invalid SL for SELL (%f <= %f)", result.stop_loss, result.entry_price)
                return False

        # Take profit validation: BUY must have TP > entry, SELL must have TP < entry
        if result.take_profit is not None:
            if result.signal == SignalType.BUY and result.take_profit <= result.entry_price:
                logger.warning("Invalid TP for BUY (%f <= %f)", result.take_profit, result.entry_price)
                return False
            if result.signal == SignalType.SELL and result.take_profit >= result.entry_price:
                logger.warning("Invalid TP for SELL (%f >= %f)", result.take_profit, result.entry_price)
                return False

        return True

    def get_stop_loss(
        self,
        price: float,
        side: SignalType,
        atr: float,
        symbol_info: Optional[Dict[str, Any]] = None,
        atr_multiplier: float = 1.5,
    ) -> float:
        """
        Calculates Stop Loss using ATR volatility or broker pip fallback.

        Args:
            price: Current entry price.
            side: SignalType (BUY or SELL).
            atr: ATR indicator value.
            symbol_info: Symbol details (e.g. digits, point).
            atr_multiplier: Multiplier for ATR distance.

        Returns:
            Computed stop loss price rounded to symbol digits.
        """
        digits = symbol_info.get("digits", 5) if symbol_info else 5
        point = symbol_info.get("point", 10 ** -digits) if symbol_info else 10 ** -digits

        if pd.notna(atr) and atr > 0:
            distance = atr * atr_multiplier
        else:
            # Fallback to default pips (1 pip = 10 points on 5-digit pairs, or 0.01 on 3-digit gold/jpy)
            pip_size = point * 10 if digits in (3, 5) else point
            distance = DEFAULT_STOP_LOSS_PIPS * pip_size

        if side == SignalType.BUY:
            sl = price - distance
        else:
            sl = price + distance

        return round(float(sl), digits)

    def get_take_profit(
        self,
        price: float,
        side: SignalType,
        atr: float,
        symbol_info: Optional[Dict[str, Any]] = None,
        risk_reward_ratio: float = 2.0,
        atr_multiplier: float = 1.5,
    ) -> float:
        """
        Calculates Take Profit maintaining a minimum Risk/Reward ratio.

        Args:
            price: Current entry price.
            side: SignalType (BUY or SELL).
            atr: ATR indicator value.
            symbol_info: Symbol details (e.g. digits, point).
            risk_reward_ratio: Desired reward-to-risk ratio.
            atr_multiplier: Multiplier for ATR distance.

        Returns:
            Computed take profit price rounded to symbol digits.
        """
        digits = symbol_info.get("digits", 5) if symbol_info else 5
        sl_price = self.get_stop_loss(price, side, atr, symbol_info, atr_multiplier)
        risk_distance = abs(price - sl_price)
        profit_distance = risk_distance * risk_reward_ratio

        if side == SignalType.BUY:
            tp = price + profit_distance
        else:
            tp = price - profit_distance

        return round(float(tp), digits)
