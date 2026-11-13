"""
Backtest Engine.

Executes rigorous historical simulation of quantitative strategies without look-ahead bias.
Supports:
- Sequential bar-by-bar candle processing
- Realistic spread, commission, and adverse slippage modeling
- In-sample / Out-of-sample train/test splits
- Walk-forward rolling window validation
- Full performance reporting and transparent assumptions disclosure
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from app.backtesting.backtest_simulator import BacktestSimulator
from app.backtesting.performance_metrics import (
    PerformanceMetricsCalculator,
    PerformanceMetricsResult,
    TradeRecord,
)
from app.core.constants import OrderSide, SignalType, TimeFrame
from app.core.logging_config import get_logger

logger = get_logger("backtesting.engine")


@dataclass
class BacktestResult:
    """Standardized backtesting output container."""

    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_balance: float
    final_balance: float
    total_bars: int
    assumptions: Dict[str, Any]
    metrics: PerformanceMetricsResult
    equity_curve: List[float] = field(default_factory=list)
    timestamps: List[str] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    in_sample_metrics: Optional[Dict[str, Any]] = None
    out_of_sample_metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_balance": self.initial_balance,
            "final_balance": round(self.final_balance, 2),
            "total_bars": self.total_bars,
            "assumptions": self.assumptions,
            "metrics": self.metrics.to_dict(),
            "trades_count": len(self.trades),
            "equity_curve": [round(x, 2) for x in self.equity_curve],
            "timestamps": self.timestamps,
            "trades": self.trades[:100],  # Return up to 100 sample trades
            "in_sample_metrics": self.in_sample_metrics,
            "out_of_sample_metrics": self.out_of_sample_metrics,
        }


class BacktestEngine:
    """
    Historical backtesting orchestrator.
    Processes historical OHLCV data sequentially to guarantee zero look-ahead contamination.
    """

    def __init__(self) -> None:
        logger.info("BacktestEngine initialized.")

    # -------------------------------------------------------------------------
    # Core Backtest Runner
    # -------------------------------------------------------------------------
    def run_backtest(
        self,
        strategy: Any,
        symbol: str,
        timeframe: Union[str, TimeFrame] = "H1",
        data: Optional[pd.DataFrame] = None,
        start_date: Optional[Union[datetime, str]] = None,
        end_date: Optional[Union[datetime, str]] = None,
        initial_balance: float = 10000.0,
        spread_pips: float = 1.5,
        slippage_pips: float = 0.3,
        commission_per_lot: float = 7.0,
        fixed_lot_size: float = 0.10,
        max_open_positions: int = 1,
        in_sample_ratio: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> BacktestResult:
        """
        Run backtest on provided data or mock data if None.

        :param strategy: BaseStrategy instance or object implementing `analyze(df)`.
        :param symbol: Instrument symbol (e.g., 'EURUSD', 'XAUUSD').
        :param timeframe: Candle timeframe.
        :param data: OHLCV DataFrame with columns ['time'/'datetime', 'open', 'high', 'low', 'close', 'volume'].
        :param start_date: Backtest start timestamp.
        :param end_date: Backtest end timestamp.
        :param initial_balance: Starting cash balance.
        :param spread_pips: Simulated bid/ask spread in pips.
        :param slippage_pips: Simulated execution slippage in pips.
        :param commission_per_lot: Round turn commission per lot.
        :param fixed_lot_size: Trading volume in lots.
        :param max_open_positions: Concurrency cap on open positions.
        :param in_sample_ratio: Optional train/test split (e.g., 0.70 for 70% in-sample).
        :param params: Optional strategy parameter overrides.
        """
        # Validate or synthesize data
        df = self._prepare_data(data, symbol, start_date, end_date)
        if len(df) < 50:
            raise ValueError(f"Insufficient historical data bars ({len(df)} bars). Minimum 50 required.")

        strat_name = getattr(strategy, "name", str(type(strategy).__name__))
        tf_str = timeframe.name if isinstance(timeframe, TimeFrame) else str(timeframe)

        assumptions = {
            "initial_balance": initial_balance,
            "spread_pips": spread_pips,
            "slippage_pips": slippage_pips,
            "commission_per_lot": commission_per_lot,
            "fixed_lot_size": fixed_lot_size,
            "max_open_positions": max_open_positions,
            "intrabar_collision_rule": "conservative_stop_loss_priority",
            "execution_delay_bars": 0,
            "params": params or {},
        }

        # Handle In-Sample / Out-of-Sample split if requested
        in_sample_metrics = None
        out_of_sample_metrics = None

        if in_sample_ratio is not None and 0.1 < in_sample_ratio < 0.9:
            split_idx = int(len(df) * in_sample_ratio)
            df_is = df.iloc[:split_idx].copy().reset_index(drop=True)
            df_oos = df.iloc[split_idx:].copy().reset_index(drop=True)

            logger.info("Executing In-Sample backtest (bars: 0..%d)", split_idx)
            res_is = self._simulate_dataset(
                strategy=strategy,
                df=df_is,
                symbol=symbol,
                initial_balance=initial_balance,
                spread_pips=spread_pips,
                slippage_pips=slippage_pips,
                commission_per_lot=commission_per_lot,
                fixed_lot_size=fixed_lot_size,
                max_open_positions=max_open_positions,
            )
            in_sample_metrics = res_is["metrics"].to_dict()

            logger.info("Executing Out-of-Sample backtest (bars: %d..%d)", split_idx, len(df))
            res_oos = self._simulate_dataset(
                strategy=strategy,
                df=df_oos,
                symbol=symbol,
                initial_balance=initial_balance,
                spread_pips=spread_pips,
                slippage_pips=slippage_pips,
                commission_per_lot=commission_per_lot,
                fixed_lot_size=fixed_lot_size,
                max_open_positions=max_open_positions,
            )
            out_of_sample_metrics = res_oos["metrics"].to_dict()

        # Run full dataset simulation
        sim_res = self._simulate_dataset(
            strategy=strategy,
            df=df,
            symbol=symbol,
            initial_balance=initial_balance,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            commission_per_lot=commission_per_lot,
            fixed_lot_size=fixed_lot_size,
            max_open_positions=max_open_positions,
        )

        start_dt_str = str(df.iloc[0]["time"]) if "time" in df.columns else str(df.index[0])
        end_dt_str = str(df.iloc[-1]["time"]) if "time" in df.columns else str(df.index[-1])

        return BacktestResult(
            strategy_name=strat_name,
            symbol=symbol.upper(),
            timeframe=tf_str,
            start_date=start_dt_str,
            end_date=end_dt_str,
            initial_balance=initial_balance,
            final_balance=sim_res["final_balance"],
            total_bars=len(df),
            assumptions=assumptions,
            metrics=sim_res["metrics"],
            equity_curve=sim_res["equity_curve"],
            timestamps=sim_res["timestamps"],
            trades=[asdict(t) for t in sim_res["trades"]],
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_of_sample_metrics,
        )

    # -------------------------------------------------------------------------
    # Dataset Sequential Simulator
    # -------------------------------------------------------------------------
    def _simulate_dataset(
        self,
        strategy: Any,
        df: pd.DataFrame,
        symbol: str,
        initial_balance: float,
        spread_pips: float,
        slippage_pips: float,
        commission_per_lot: float,
        fixed_lot_size: float,
        max_open_positions: int,
    ) -> Dict[str, Any]:
        """
        Step-by-step sequential bar iteration.
        Guarantees zero look-ahead bias.
        """
        sim = BacktestSimulator(
            symbol=symbol,
            initial_balance=initial_balance,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            commission_per_lot=commission_per_lot,
        )

        # Minimum warmup period for indicators (e.g. 30 bars)
        warmup_bars = 30
        timestamps: List[str] = []

        for i in range(len(df)):
            current_bar = df.iloc[i]
            ts = current_bar["time"] if "time" in current_bar else datetime.now(timezone.utc)
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.now(timezone.utc)

            timestamps.append(ts.isoformat() if hasattr(ts, "isoformat") else str(ts))

            open_p = float(current_bar["open"])
            high_p = float(current_bar["high"])
            low_p = float(current_bar["low"])
            close_p = float(current_bar["close"])

            # 1. Intrabar evaluation: Check existing open positions against current bar's H/L
            sim.evaluate_bar(
                bar_idx=i,
                timestamp=ts,
                open_p=open_p,
                high_p=high_p,
                low_p=low_p,
                close_p=close_p,
            )

            # Skip trading signals during warmup
            if i < warmup_bars:
                continue

            # 2. Strict no-lookahead: strategy only receives data up to bar i
            sub_df = df.iloc[: i + 1]

            try:
                if hasattr(strategy, "analyze"):
                    res = strategy.analyze(sub_df)
                elif callable(strategy):
                    res = strategy(sub_df)
                else:
                    res = None
            except Exception as e:
                logger.debug("Strategy evaluation error on bar %d: %s", i, e)
                res = None

            if res is None:
                continue

            # Determine signal
            sig_side = getattr(res, "signal", None)
            if sig_side is None and isinstance(res, dict):
                sig_side = res.get("signal")

            if sig_side in (SignalType.BUY, "BUY", OrderSide.BUY, "buy"):
                side = OrderSide.BUY
            elif sig_side in (SignalType.SELL, "SELL", OrderSide.SELL, "sell"):
                side = OrderSide.SELL
            else:
                side = None

            # Execute entry if actionable and within limits
            if side is not None and len(sim.open_positions) < max_open_positions:
                entry_p = close_p  # Signal evaluated on bar close; entry price is close_p
                sl = getattr(res, "stop_loss", None) if not isinstance(res, dict) else res.get("stop_loss")
                tp = getattr(res, "take_profit", None) if not isinstance(res, dict) else res.get("take_profit")

                sim.open_order(
                    side=side,
                    volume=fixed_lot_size,
                    market_price=entry_p,
                    sl=sl,
                    tp=tp,
                    bar_idx=i,
                    timestamp=ts,
                )

        # Close any lingering positions on the final bar at close price
        last_bar = df.iloc[-1]
        last_ts = last_bar["time"] if "time" in last_bar else datetime.now(timezone.utc)
        if isinstance(last_ts, str):
            try:
                last_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            except Exception:
                last_ts = datetime.now(timezone.utc)

        final_price = float(last_bar["close"])
        for pos_id in list(sim.open_positions.keys()):
            sim.close_order(pos_id, final_price, last_ts, reason="end_of_backtest")

        metrics = PerformanceMetricsCalculator.calculate(
            trades=sim.closed_trades,
            equity_curve=sim.equity_curve,
            initial_balance=initial_balance,
        )

        return {
            "metrics": metrics,
            "final_balance": sim.balance,
            "equity_curve": sim.equity_curve,
            "timestamps": timestamps,
            "trades": sim.closed_trades,
        }

    # -------------------------------------------------------------------------
    # Walk-Forward Testing
    # -------------------------------------------------------------------------
    def run_walk_forward(
        self,
        strategy: Any,
        symbol: str,
        timeframe: Union[str, TimeFrame] = "H1",
        data: Optional[pd.DataFrame] = None,
        windows: int = 4,
        train_ratio: float = 0.7,
        initial_balance: float = 10000.0,
        fixed_lot_size: float = 0.10,
    ) -> List[Dict[str, Any]]:
        """
        Execute Walk-Forward analysis across rolling train / test windows.
        """
        df = self._prepare_data(data, symbol)
        total_len = len(df)
        window_size = int(total_len / windows)
        results: List[Dict[str, Any]] = []

        for w in range(windows):
            start_idx = w * (window_size // 2)
            end_idx = min(start_idx + window_size, total_len)
            sub_slice = df.iloc[start_idx:end_idx].reset_index(drop=True)

            if len(sub_slice) < 60:
                continue

            res = self.run_backtest(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                data=sub_slice,
                initial_balance=initial_balance,
                fixed_lot_size=fixed_lot_size,
                in_sample_ratio=train_ratio,
            )

            results.append({
                "window": w + 1,
                "start_idx": start_idx,
                "end_idx": end_idx,
                "total_bars": len(sub_slice),
                "in_sample_metrics": res.in_sample_metrics,
                "out_of_sample_metrics": res.out_of_sample_metrics,
                "overall_win_rate": res.metrics.win_rate,
                "overall_net_profit": res.metrics.net_profit,
                "profit_factor": res.metrics.profit_factor,
            })

        logger.info("Completed %d walk-forward validation windows.", len(results))
        return results

    # -------------------------------------------------------------------------
    # Data Preparation Helper
    # -------------------------------------------------------------------------
    def _prepare_data(
        self,
        data: Optional[pd.DataFrame],
        symbol: str,
        start_date: Optional[Union[datetime, str]] = None,
        end_date: Optional[Union[datetime, str]] = None,
    ) -> pd.DataFrame:
        """Sanitize or generate synthetic backtesting data if none provided."""
        if data is not None and not data.empty:
            df = data.copy()
            # Standardize column names to lowercase
            df.columns = [c.lower() for c in df.columns]

            # Ensure required OHLC columns exist
            for col in ["open", "high", "low", "close"]:
                if col not in df.columns:
                    raise ValueError(f"Missing required column '{col}' in backtest DataFrame.")

            # Filter date range if specified
            if "time" in df.columns and (start_date or end_date):
                df["time_dt"] = pd.to_datetime(df["time"])
                if start_date:
                    df = df[df["time_dt"] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df["time_dt"] <= pd.to_datetime(end_date)]
                df = df.drop(columns=["time_dt"])

            return df.reset_index(drop=True)

        # Generate realistic synthetic data for testing if no raw data supplied
        logger.info("No data provided; generating synthetic geometric random walk bars for %s", symbol)
        n_bars = 500
        base_price = 2650.0 if "XAU" in symbol.upper() else 1.0850
        volatility = 0.003 if "XAU" in symbol.upper() else 0.0008

        np.random.seed(42)
        returns = np.random.normal(0, volatility, n_bars)
        price_series = base_price * np.exp(np.cumsum(returns))

        dates = pd.date_range(end=datetime.now(timezone.utc), periods=n_bars, freq="15min")
        opens = price_series
        highs = opens * (1.0 + np.abs(np.random.normal(0, volatility / 2, n_bars)))
        lows = opens * (1.0 - np.abs(np.random.normal(0, volatility / 2, n_bars)))
        closes = opens * (1.0 + np.random.normal(0, volatility / 2, n_bars))
        volumes = np.random.randint(100, 2000, n_bars)

        synth_df = pd.DataFrame({
            "time": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })
        return synth_df
