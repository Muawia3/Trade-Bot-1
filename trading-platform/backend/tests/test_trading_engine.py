"""
Comprehensive Unit & Integration Tests for Trading Engine, Paper Trading,
Backtesting, Portfolio Management, and Notifications.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    import pytest
except ImportError:
    pytest = None
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from app.core.config import get_settings, TradingMode
from app.core.constants import OrderSide, OrderStatus, OrderType, SignalType
from app.paper_trading.paper_engine import (
    PaperTradingEngine,
    PaperPosition,
    PaperTradeResult,
)
from app.paper_trading.paper_account_manager import (
    PaperAccountManager,
    get_paper_account_manager,
)
from app.execution.trade_executor import TradeExecutor, TradeResult
from app.execution.order_manager import OrderManager, PendingOrder
from app.backtesting.backtest_simulator import BacktestSimulator
from app.backtesting.performance_metrics import (
    PerformanceMetricsCalculator,
    TradeRecord,
)
from app.backtesting.backtest_engine import BacktestEngine
from app.portfolio.portfolio_manager import PortfolioManager
from app.portfolio.portfolio_analytics import PortfolioAnalytics
from app.notifications.notification_service import (
    NotificationService,
    NotificationType,
    NotificationSeverity,
)
from app.strategies.trend_following import TrendFollowingStrategy


# =============================================================================
# 1. Paper Trading Engine Tests
# =============================================================================

def test_paper_engine_open_and_close():
    engine = PaperTradingEngine(initial_balance=10000.0, commission_per_lot=7.0, slippage_pips=0.2)

    # 1. Open BUY position on EURUSD (price: 1.0850, SL: 1.0800, TP: 1.0950)
    result = engine.open_position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=0.10,
        price=1.0850,
        sl=1.0800,
        tp=1.0950,
        comment="Test Buy",
    )

    assert result.success is True
    assert result.position_id is not None
    assert engine.balance < 10000.0  # Commission deducted ($0.70)
    assert len(engine.positions) == 1

    pos = engine.get_position(result.position_id)
    assert pos is not None
    assert pos.symbol == "EURUSD"
    assert pos.volume == 0.10

    # 2. Update price favorably (1.0890)
    events = engine.update_positions({"EURUSD": {"bid": 1.0890, "ask": 1.0892}})
    assert pos.unrealized_pnl > 0
    assert engine.equity > engine.balance

    # 3. Close position
    close_res = engine.close_position(pos.id, price=1.0890, reason="manual_test")
    assert close_res.success is True
    assert close_res.realized_pnl > 0
    assert len(engine.positions) == 0
    assert len(engine.history) == 1
    assert engine.balance > 10000.0  # Net profit realized


def test_paper_engine_sl_tp_triggers():
    engine = PaperTradingEngine(initial_balance=10000.0, slippage_pips=0.0)

    # Open Buy on XAUUSD (Gold)
    res = engine.open_position(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.10,
        price=2680.00,
        sl=2675.00,
        tp=2695.00,
    )
    pos_id = res.position_id

    # Simulate price drop to trigger SL (2674.50 <= 2675.00)
    events = engine.update_positions({"XAUUSD": {"bid": 2674.50, "ask": 2674.80}})
    assert len(events) >= 1
    assert events[0]["type"] == "ORDER_STOP_LOSS"
    assert pos_id not in engine.positions
    assert len(engine.history) == 1
    assert engine.history[0].close_reason == "stop_loss"


def test_paper_engine_trailing_stop():
    engine = PaperTradingEngine(initial_balance=10000.0, slippage_pips=0.0)

    # Open Buy with 30 pips trailing stop (0.0030 for EURUSD)
    res = engine.open_position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=0.10,
        price=1.0800,
        sl=1.0750,
        trailing_stop_pips=30.0,
    )
    pos_id = res.position_id
    pos = engine.get_position(pos_id)
    initial_sl = pos.sl

    # Price advances to 1.0850 (50 pips profit)
    events = engine.update_positions({"EURUSD": {"bid": 1.0850, "ask": 1.0851}})
    # Trailing stop should have moved up to 1.0850 - 0.0030 = 1.0820
    assert pos.sl is not None
    assert pos.sl > initial_sl
    assert any(ev["type"] == "TRAILING_STOP_MOVED" for ev in events)


def test_paper_engine_partial_close():
    engine = PaperTradingEngine(initial_balance=10000.0, slippage_pips=0.0)
    res = engine.open_position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=0.20,
        price=1.0800,
        sl=1.0750,
        tp=1.0900,
    )
    pos_id = res.position_id

    # Partial close 0.10 lots at 1.0850
    partial_res = engine.partial_close(pos_id, volume_to_close=0.10, price=1.0850)
    assert partial_res.success is True
    assert partial_res.realized_pnl > 0

    pos = engine.get_position(pos_id)
    assert pos.volume == 0.10
    assert len(engine.history) == 1  # 0.10 closed trade recorded in history


def test_paper_account_manager():
    mgr = PaperAccountManager()
    acc_info = mgr.create_account(name="Scalping Account", initial_balance=5000.0)
    assert acc_info.account_id in mgr.accounts

    engine = mgr.get_account_engine(acc_info.account_id)
    assert engine.balance == 5000.0

    perf = mgr.get_account_performance(acc_info.account_id)
    assert perf["total_trades"] == 0
    assert perf["balance"] == 5000.0

    mgr.delete_account(acc_info.account_id)
    assert acc_info.account_id not in mgr.accounts


# =============================================================================
# 2. Execution Engine & Order Manager Tests
# =============================================================================

def test_trade_executor_pre_trade_checklist_rejections():
    executor = TradeExecutor()
    acc_info = {"equity": 10000.0, "balance": 10000.0, "free_margin": 10000.0, "open_positions_count": 0}
    sym_info = {"pip_size": 0.0001, "spread_pips": 1.0, "volume_min": 0.01, "volume_max": 100.0}

    # 1. Missing stop loss -> REJECT
    passed, reason, _ = executor.pre_trade_checklist(
        symbol="EURUSD",
        side=OrderSide.BUY,
        entry_price=1.0800,
        sl=None,
        tp=1.0900,
        volume=0.10,
        account_info=acc_info,
        symbol_info=sym_info,
    )
    assert passed is False
    assert "Stop Loss" in reason

    # 2. Spread too wide -> REJECT
    sym_wide_spread = dict(sym_info, spread_pips=10.0)
    passed, reason, _ = executor.pre_trade_checklist(
        symbol="EURUSD",
        side=OrderSide.BUY,
        entry_price=1.0800,
        sl=1.0750,
        tp=1.0900,
        volume=0.10,
        account_info=acc_info,
        symbol_info=sym_wide_spread,
        risk_params={"max_spread_pips": 3.0},
    )
    assert passed is False
    assert "Spread too wide" in reason

    # 3. Invalid SL orientation (BUY SL >= entry) -> REJECT
    passed, reason, _ = executor.pre_trade_checklist(
        symbol="EURUSD",
        side=OrderSide.BUY,
        entry_price=1.0800,
        sl=1.0850,
        tp=1.0900,
        volume=0.10,
        account_info=acc_info,
        symbol_info=sym_info,
    )
    assert passed is False
    assert "Invalid Buy SL" in reason


def test_trade_executor_position_sizing():
    executor = TradeExecutor()
    equity = 10000.0
    risk_pct = 1.0  # $100 risk
    entry = 1.0800
    sl = 1.0750    # 50 pips distance
    # For EURUSD: 50 pips * $10/pip/lot = $500 risk per standard lot
    # $100 / $500 = 0.20 lots
    lot = executor.calculate_position_size(
        symbol="EURUSD",
        entry_price=entry,
        stop_loss=sl,
        account_equity=equity,
        risk_percent=risk_pct,
    )
    assert lot == 0.20


def test_trade_executor_safe_paper_routing():
    paper_engine = PaperTradingEngine(initial_balance=10000.0)
    executor = TradeExecutor(paper_engine=paper_engine)

    signal = {
        "symbol": "EURUSD",
        "signal_type": "BUY",
        "entry_price": 1.0850,
        "stop_loss": 1.0800,
        "take_profit": 1.0950,
        "strategy_name": "TestTrend",
        "confidence": 0.85,
    }
    acc_info = {"equity": 10000.0, "balance": 10000.0, "free_margin": 10000.0, "open_positions_count": 0}
    sym_info = {"pip_size": 0.0001, "spread_pips": 1.2, "trade_mode_open": True}

    res = executor.execute_signal(signal, acc_info, sym_info)
    assert res.success is True
    assert res.trading_mode == "PAPER"
    assert len(paper_engine.positions) == 1


def test_order_manager_break_even():
    paper_engine = PaperTradingEngine(initial_balance=10000.0, slippage_pips=0.0)
    manager = OrderManager(paper_engine=paper_engine)

    # Open Buy at 1.0800, SL at 1.0750
    paper_engine.open_position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=0.10,
        price=1.0800,
        sl=1.0750,
    )
    pos = paper_engine.get_open_positions()[0]

    # Price moves up 25 pips (>= 20 pips break even threshold)
    events = manager.monitor_positions(
        current_prices={"EURUSD": {"bid": 1.0825, "ask": 1.0826}},
        break_even_pips=20.0,
    )
    assert any(ev.get("type") == "BREAK_EVEN_TRIGGERED" for ev in events)
    assert pos.sl >= 1.0800  # SL protected at or above open price


# =============================================================================
# 3. Backtesting Engine Tests
# =============================================================================

def test_performance_metrics_calculator():
    # Construct sample closed trades
    now = datetime.now(timezone.utc)
    trades = [
        TradeRecord("t1", "EURUSD", "BUY", now - timedelta(hours=2), now - timedelta(hours=1), 1.08, 1.085, 0.1, 50.0, 50.7, 0.7),
        TradeRecord("t2", "EURUSD", "BUY", now - timedelta(hours=4), now - timedelta(hours=3), 1.08, 1.075, 0.1, -50.0, -49.3, 0.7),
        TradeRecord("t3", "EURUSD", "BUY", now - timedelta(hours=6), now - timedelta(hours=5), 1.08, 1.090, 0.1, 100.0, 100.7, 0.7),
    ]
    equity_curve = [10000.0, 10050.0, 10000.0, 10100.0]

    metrics = PerformanceMetricsCalculator.calculate(
        trades=trades,
        equity_curve=equity_curve,
        initial_balance=10000.0,
    )

    assert metrics.total_trades == 3
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert round(metrics.win_rate, 1) == 66.7
    assert metrics.net_profit == 100.0
    assert metrics.gross_profit == 150.0
    assert metrics.gross_loss == 50.0
    assert metrics.profit_factor == 3.0


def test_backtest_engine_run():
    engine = BacktestEngine()
    strategy = TrendFollowingStrategy(symbol="EURUSD", timeframe="H1")

    # Generate synthetic 100 bars
    np.random.seed(123)
    bars = 120
    dates = pd.date_range("2024-01-01", periods=bars, freq="1h")
    prices = 1.0800 + np.cumsum(np.random.normal(0, 0.0005, bars))

    df = pd.DataFrame({
        "time": dates,
        "open": prices,
        "high": prices + 0.0005,
        "low": prices - 0.0005,
        "close": prices,
        "volume": np.random.randint(100, 1000, bars),
    })

    result = engine.run_backtest(
        strategy=strategy,
        symbol="EURUSD",
        timeframe="H1",
        data=df,
        initial_balance=10000.0,
        spread_pips=1.0,
        fixed_lot_size=0.10,
    )

    assert result.strategy_name == strategy.name
    assert result.symbol == "EURUSD"
    assert len(result.equity_curve) > 0
    assert result.metrics is not None
    assert result.metrics.total_trades >= 0


def test_backtest_intrabar_conservative_collision():
    sim = BacktestSimulator(symbol="EURUSD", initial_balance=10000.0, spread_pips=0.0, slippage_pips=0.0)
    now = datetime.now(timezone.utc)

    # Open Buy at 1.0800 with SL 1.0780 and TP 1.0850
    pos = sim.open_order(
        side=OrderSide.BUY,
        volume=0.10,
        market_price=1.0800,
        sl=1.0780,
        tp=1.0850,
        bar_idx=0,
        timestamp=now,
    )

    # Candle that hits BOTH SL (low 1.0770) and TP (high 1.0860)
    closed = sim.evaluate_bar(
        bar_idx=1,
        timestamp=now + timedelta(hours=1),
        open_p=1.0800,
        high_p=1.0860,
        low_p=1.0770,
        close_p=1.0810,
    )

    assert len(closed) == 1
    # Must conservatively record stop_loss_collision, never optimistic take_profit
    assert "stop_loss" in closed[0].exit_reason
    assert closed[0].net_pnl < 0


# =============================================================================
# 4. Portfolio Management Tests
# =============================================================================

def test_portfolio_manager_heat_and_exposure():
    engine = PaperTradingEngine(initial_balance=10000.0, slippage_pips=0.0)
    pm = PortfolioManager(paper_engine=engine, max_portfolio_heat_percent=10.0)

    # Open 2 positions
    engine.open_position("EURUSD", OrderSide.BUY, 0.10, 1.0800, sl=1.0750)  # $50 at risk
    engine.open_position("XAUUSD", OrderSide.BUY, 0.10, 2680.0, sl=2670.0)  # $100 at risk

    exposure = pm.calculate_total_exposure()
    assert exposure["total_open_positions"] == 2
    assert "EURUSD" in exposure["symbols_active"]
    assert "XAUUSD" in exposure["symbols_active"]

    heat = pm.calculate_portfolio_heat()
    assert heat["total_risk_usd"] > 0
    assert heat["portfolio_heat_percent"] < 10.0
    assert heat["is_safe"] is True


def test_portfolio_correlation():
    pm = PortfolioManager()
    np.random.seed(42)
    # Generate positively correlated price series
    x = np.cumsum(np.random.normal(0, 0.01, 100))
    y = x + np.random.normal(0, 0.002, 100)

    df = pd.DataFrame({"XAUUSD": x + 2000, "EURUSD": y + 1.08})
    corr = pm.calculate_correlation(df, "XAUUSD", "EURUSD")
    assert corr > 0.80  # Strong positive correlation detected


# =============================================================================
# 5. Notification Service Tests
# =============================================================================

def test_notification_service():
    service = NotificationService(max_history_size=50)

    received = []
    service.register_listener(lambda n: received.append(n))

    notif = service.notify_risk_alert(
        title="High Heat Warning",
        message="Portfolio heat exceeded 8%",
        severity=NotificationSeverity.WARNING,
    )

    assert notif.id is not None
    assert len(received) == 1
    assert received[0].severity == NotificationSeverity.WARNING

    history = service.get_history(limit=10)
    assert len(history) == 1
    assert history[0]["title"] == "High Heat Warning"

    service.mark_as_read(notif.id)
    assert service.get_history(unread_only=True) == []


# =============================================================================
# 6. Trading Service & Analytics Service Tests
# =============================================================================

def test_services_integration():
    import asyncio
    from app.services.trading_service import TradingService
    from app.services.analytics_service import AnalyticsService

    # 1. TradingService single cycle
    trading_svc = TradingService(monitored_symbols=["EURUSD", "XAUUSD"])
    assert trading_svc.status.is_running is False
    assert "EURUSD" in trading_svc.status.monitored_symbols

    # Run one evaluation cycle synchronously
    cycle_res = asyncio.run(trading_svc.run_once())
    assert "signals" in cycle_res
    assert "position_events" in cycle_res
    assert trading_svc.status.total_cycles_completed == 1

    # 2. AnalyticsService dashboard metrics
    analytics_svc = AnalyticsService(paper_engine=trading_svc.paper_engine)
    dashboard = analytics_svc.get_dashboard_summary()
    assert "account" in dashboard
    assert "performance" in dashboard
    assert "portfolio" in dashboard
    assert dashboard["account"]["balance"] > 0

    curve = analytics_svc.get_equity_curve()
    assert "series" in curve
    assert len(curve["series"]) >= 1


if __name__ == "__main__":
    if pytest is not None:
        pytest.main(["-v", __file__])
    else:
        test_funcs = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
        passed = 0
        for fn in test_funcs:
            fn()
            passed += 1
            print(f"PASS: {fn.__name__}")
        print(f"All {passed} tests passed!")
