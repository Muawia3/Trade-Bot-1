"""
Portfolio Manager.

Tracks multi-asset open exposures, portfolio heat (total capital at risk),
unrealized P/L, position aggregations by symbol, and real-time correlation
monitoring between key trading instruments (e.g. XAUUSD vs EURUSD).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.core.constants import OrderSide, TARGET_INSTRUMENTS
from app.core.logging_config import get_logger
from app.paper_trading.paper_engine import PaperPosition, PaperTradingEngine

logger = get_logger("portfolio.manager")


@dataclass
class InstrumentPositionSummary:
    """Aggregated position summary for a single trading symbol."""

    symbol: str
    net_volume: float  # Positive for net Long, negative for net Short
    total_long_volume: float
    total_short_volume: float
    open_positions_count: int
    average_long_price: float = 0.0
    average_short_price: float = 0.0
    unrealized_pnl: float = 0.0
    total_risk_amount: float = 0.0  # Dollar amount at risk based on Stop Losses
    notional_usd_exposure: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "net_volume": round(self.net_volume, 2),
            "total_long_volume": round(self.total_long_volume, 2),
            "total_short_volume": round(self.total_short_volume, 2),
            "open_positions_count": self.open_positions_count,
            "average_long_price": round(self.average_long_price, 5),
            "average_short_price": round(self.average_short_price, 5),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_risk_amount": round(self.total_risk_amount, 2),
            "notional_usd_exposure": round(self.notional_usd_exposure, 2),
        }


class PortfolioManager:
    """
    Oversees holistic account risk, exposure balancing, and asset correlation.
    """

    def __init__(
        self,
        paper_engine: Optional[PaperTradingEngine] = None,
        max_portfolio_heat_percent: float = 10.0,
        max_single_symbol_exposure_lots: float = 5.0,
    ) -> None:
        self.settings = get_settings()
        self.paper_engine = paper_engine or PaperTradingEngine()
        self.max_portfolio_heat_percent = max_portfolio_heat_percent
        self.max_single_symbol_exposure_lots = max_single_symbol_exposure_lots

        # Correlation cache: {(symbol_a, symbol_b): (correlation_value, timestamp)}
        self._correlation_cache: Dict[Tuple[str, str], Tuple[float, datetime]] = {}

        logger.info(
            "PortfolioManager initialized. Max Heat: %.1f%%, Max Symbol Lots: %.2f",
            self.max_portfolio_heat_percent,
            self.max_single_symbol_exposure_lots,
        )

    # -------------------------------------------------------------------------
    # Position Summaries & Exposures
    # -------------------------------------------------------------------------
    def get_all_positions(self) -> List[PaperPosition]:
        """Fetch all currently open positions from trading engine."""
        return self.paper_engine.get_open_positions()

    def get_instrument_summaries(self) -> Dict[str, InstrumentPositionSummary]:
        """Aggregate open positions by instrument."""
        positions = self.get_all_positions()
        summaries: Dict[str, InstrumentPositionSummary] = {}

        for pos in positions:
            sym = pos.symbol.upper()
            if sym not in summaries:
                summaries[sym] = InstrumentPositionSummary(
                    symbol=sym,
                    net_volume=0.0,
                    total_long_volume=0.0,
                    total_short_volume=0.0,
                    open_positions_count=0,
                )

            s = summaries[sym]
            s.open_positions_count += 1
            s.unrealized_pnl += pos.unrealized_pnl

            # Calculate contract specifications
            specs = self.paper_engine.get_symbol_specs(sym)
            contract_size = specs["contract_size"]

            # Calculate risk amount if SL is defined
            risk_for_pos = 0.0
            if pos.sl is not None and pos.sl > 0:
                price_diff = abs(pos.open_price - pos.sl)
                risk_for_pos = price_diff * contract_size * pos.volume
            s.total_risk_amount += risk_for_pos

            # Notional exposure in USD
            s.notional_usd_exposure += pos.volume * contract_size * pos.current_price

            # Volume breakdown
            if pos.side == OrderSide.BUY:
                s.total_long_volume += pos.volume
                s.net_volume += pos.volume
            else:
                s.total_short_volume += pos.volume
                s.net_volume -= pos.volume

        return summaries

    def calculate_total_exposure(self) -> Dict[str, Any]:
        """
        Calculate total exposure across all instruments.
        Returns total notional volume, net lots, and breakdown by currency/commodity.
        """
        summaries = self.get_instrument_summaries()
        total_notional_usd = sum(s.notional_usd_exposure for s in summaries.values())
        total_open_lots = sum(s.total_long_volume + s.total_short_volume for s in summaries.values())
        total_positions_count = sum(s.open_positions_count for s in summaries.values())

        by_symbol = {sym: s.to_dict() for sym, s in summaries.items()}

        return {
            "total_notional_usd": round(total_notional_usd, 2),
            "total_open_lots": round(total_open_lots, 2),
            "total_open_positions": total_positions_count,
            "symbols_active": list(summaries.keys()),
            "by_symbol": by_symbol,
        }

    def calculate_total_unrealized_pnl(self) -> float:
        """Calculate aggregate unrealized PnL across all open positions."""
        positions = self.get_all_positions()
        return round(sum(p.unrealized_pnl for p in positions), 2)

    # -------------------------------------------------------------------------
    # Portfolio Heat
    # -------------------------------------------------------------------------
    def calculate_portfolio_heat(self, account_equity: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate Portfolio Heat: percentage of current equity at risk
        if every open position were to hit its Stop Loss simultaneously.
        """
        summary = self.paper_engine.get_account_summary()
        equity = account_equity if account_equity is not None else summary["equity"]

        if equity <= 0:
            return {"portfolio_heat_percent": 0.0, "total_risk_usd": 0.0, "equity": equity, "is_safe": False}

        summaries = self.get_instrument_summaries()
        total_risk_usd = sum(s.total_risk_amount for s in summaries.values())
        heat_pct = (total_risk_usd / equity) * 100.0

        is_safe = heat_pct <= self.max_portfolio_heat_percent

        return {
            "portfolio_heat_percent": round(heat_pct, 2),
            "total_risk_usd": round(total_risk_usd, 2),
            "max_allowed_heat_percent": self.max_portfolio_heat_percent,
            "equity": round(equity, 2),
            "is_safe": is_safe,
        }

    # -------------------------------------------------------------------------
    # Correlation Monitoring
    # -------------------------------------------------------------------------
    def calculate_correlation(
        self,
        prices_df: pd.DataFrame,
        symbol_a: str = "XAUUSD",
        symbol_b: str = "EURUSD",
        window: int = 50,
    ) -> float:
        """
        Calculate Pearson correlation between two instruments over a rolling window of prices.
        """
        sym_a = symbol_a.upper()
        sym_b = symbol_b.upper()

        if prices_df is None or prices_df.empty:
            return 0.0

        cols = [c.upper() for c in prices_df.columns]
        if sym_a not in cols or sym_b not in cols:
            logger.debug("One or both symbols (%s, %s) missing from price matrix for correlation.", sym_a, sym_b)
            return 0.0

        # Calculate percentage returns
        returns_a = prices_df[sym_a].pct_change().dropna().tail(window)
        returns_b = prices_df[sym_b].pct_change().dropna().tail(window)

        if len(returns_a) < 10 or len(returns_b) < 10:
            return 0.0

        corr = float(np.corrcoef(returns_a, returns_b)[0, 1])
        corr = float(np.nan_to_num(corr, nan=0.0))

        self._correlation_cache[(sym_a, sym_b)] = (corr, datetime.now(timezone.utc))
        return round(corr, 4)

    def check_correlation_risk(
        self,
        symbol_a: str = "XAUUSD",
        symbol_b: str = "EURUSD",
        current_correlation: Optional[float] = None,
        threshold: float = 0.70,
    ) -> Dict[str, Any]:
        """
        Evaluate if opening simultaneous positions in correlated pairs increases risk.
        For example: Gold (XAUUSD) and EURUSD frequently have high positive correlation
        against the US Dollar. Holding Long XAUUSD and Long EURUSD doubles USD short exposure.
        """
        corr = current_correlation
        if corr is None:
            cached = self._correlation_cache.get((symbol_a.upper(), symbol_b.upper()))
            corr = cached[0] if cached else 0.50  # Default historical approx if not yet computed

        summaries = self.get_instrument_summaries()
        sum_a = summaries.get(symbol_a.upper())
        sum_b = summaries.get(symbol_b.upper())

        has_a = sum_a is not None and abs(sum_a.net_volume) > 0.001
        has_b = sum_b is not None and abs(sum_b.net_volume) > 0.001

        is_correlated_risk = False
        warning_msg = "Correlated exposure is within normal bounds."

        if has_a and has_b and corr is not None:
            same_direction = (sum_a.net_volume > 0 and sum_b.net_volume > 0) or (
                sum_a.net_volume < 0 and sum_b.net_volume < 0
            )

            if abs(corr) >= threshold and same_direction:
                is_correlated_risk = True
                warning_msg = (
                    f"Elevated correlation risk detected: {symbol_a} and {symbol_b} "
                    f"have a correlation of {corr:.2f} and both hold net "
                    f"{'LONG' if sum_a.net_volume > 0 else 'SHORT'} exposure."
                )
                logger.warning(warning_msg)

        return {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "correlation": round(corr, 2) if corr is not None else 0.0,
            "has_exposure_a": has_a,
            "has_exposure_b": has_b,
            "is_correlated_risk": is_correlated_risk,
            "warning": warning_msg,
        }

    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        """Return a complete, real-time snapshot of the portfolio state."""
        heat = self.calculate_portfolio_heat()
        exposure = self.calculate_total_exposure()
        unrealized = self.calculate_total_unrealized_pnl()
        corr_risk = self.check_correlation_risk("XAUUSD", "EURUSD")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "unrealized_pnl": unrealized,
            "portfolio_heat": heat,
            "exposure": exposure,
            "correlation_analysis": corr_risk,
        }
