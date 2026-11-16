"""
=============================================================================
         EXNESS MT5 DIRECT AUTO-TRADING BOT (XAU/USD & EUR/USD)
=============================================================================
Features:
- Dynamic Command & Rules Hot-Reloading from bot_commands.json
- Direct execution in MetaTrader 5 (Exness)
- Institutional H1 Trend + M5 Value Pullback Strategy
- H4 Support & Resistance Engulfing Strategy (1:2 Dynamic R:R)
- Smart Break-Even (Risk-Free at 1R) & Breathing Trailing Stop
- Symbol-Aware Pips & Dollars for Gold and Forex
- Anti-Overtrading Cooldown & Session Liquidity Filters
=============================================================================
"""

import os
import sys
import time
import math
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, List, Any

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[ERROR] MetaTrader5 library is not installed. Run: pip install MetaTrader5")
    sys.exit(1)

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("[ERROR] pandas/numpy not installed. Run: pip install pandas numpy")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("exness_bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("ExnessBot")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMANDS_FILE = os.path.join(SCRIPT_DIR, "bot_commands.json")


# =============================================================================
# DYNAMIC COMMAND MANAGER (HOT RELOAD FROM bot_commands.json)
# =============================================================================
class CommandManager:
    """Monitors and dynamically reloads bot_commands.json in real-time."""

    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }

    def __init__(self, filepath: str = COMMANDS_FILE):
        self.filepath = filepath
        self.last_mtime: float = 0.0
        self.commands: dict = {}
        self.load(initial=True)

    def load(self, initial: bool = False) -> bool:
        """Read and parse bot_commands.json."""
        if not os.path.exists(self.filepath):
            if initial:
                logger.warning(f"Commands file '{self.filepath}' not found. Using default internal rules.")
            return False

        try:
            mtime = os.path.getmtime(self.filepath)
            if mtime != self.last_mtime:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.commands = json.load(f)
                self.last_mtime = mtime

                gen = self.commands.get("general", {})
                risk = self.commands.get("money_and_risk", {})
                strat = self.commands.get("advanced_strategy", self.commands.get("strategy_settings", {}))

                if not initial:
                    logger.info("=" * 65)
                    logger.info("🔄 [COMMANDS UPDATED] Loaded new instructions from bot_commands.json:")
                    logger.info(f"   Active Pairs : {gen.get('active_symbols', ['XAUUSD', 'EURUSD'])}")
                    logger.info(f"   Trading Side : {gen.get('trading_side', 'BOTH')}")
                    logger.info(f"   Lot Sizing   : {'Fixed ' + str(risk.get('lot_size', 0.01)) if risk.get('use_fixed_lot', False) else 'Dynamic ' + str(risk.get('risk_percent_per_trade', 1.0)) + '%'}")
                    logger.info(f"   Timeframe    : {strat.get('entry_timeframe', 'M5')}")
                    logger.info(f"   Paused       : {gen.get('pause_trading', False)}")
                    logger.info("=" * 65)
                return True
        except Exception as e:
            logger.error(f"Error parsing {self.filepath}: {e}")
        return False

    # --- General Getters ---
    @property
    def pause_trading(self) -> bool:
        return bool(self.commands.get("general", {}).get("pause_trading", False))

    @property
    def trading_side(self) -> str:
        return self.commands.get("general", {}).get("trading_side", "BOTH").upper()

    @property
    def active_symbols(self) -> List[str]:
        return self.commands.get("general", {}).get("active_symbols", ["XAUUSD", "EURUSD"])

    @property
    def check_interval(self) -> int:
        return int(self.commands.get("general", {}).get("check_interval_seconds", 10))

    # --- Money & Risk Management ---
    @property
    def lot_size(self) -> float:
        return float(self.commands.get("money_and_risk", {}).get("lot_size", 0.01))

    @property
    def use_fixed_lot(self) -> bool:
        return bool(self.commands.get("money_and_risk", {}).get("use_fixed_lot", False))

    @property
    def risk_percent(self) -> float:
        return float(self.commands.get("money_and_risk", {}).get("risk_percent_per_trade", 1.0))

    @property
    def min_lot_limit(self) -> float:
        return float(self.commands.get("money_and_risk", {}).get("min_lot_size_limit", 0.01))

    @property
    def max_lot_limit(self) -> float:
        return float(self.commands.get("money_and_risk", {}).get("max_lot_size_limit", 0.50))

    @property
    def max_open_per_pair(self) -> int:
        return int(self.commands.get("money_and_risk", {}).get("max_open_positions_per_pair", 1))

    @property
    def max_total_open(self) -> int:
        return int(self.commands.get("money_and_risk", {}).get("max_total_open_positions", 2))

    @property
    def max_daily_trades(self) -> int:
        return int(self.commands.get("money_and_risk", {}).get("max_daily_trades", 8))

    @property
    def trade_cooldown_minutes(self) -> int:
        return int(self.commands.get("money_and_risk", {}).get("trade_cooldown_minutes", 25))

    @property
    def max_daily_loss(self) -> float:
        return float(self.commands.get("money_and_risk", {}).get("max_daily_loss_usd", 30.0))

    # --- Advanced Strategy Settings ---
    @property
    def timeframe(self) -> int:
        strat = self.commands.get("advanced_strategy", self.commands.get("strategy_settings", {}))
        tf_str = strat.get("entry_timeframe", strat.get("timeframe", "M5")).upper()
        return self.TIMEFRAME_MAP.get(tf_str, mt5.TIMEFRAME_M5)

    @property
    def fast_ema(self) -> int:
        return int(self.commands.get("advanced_strategy", {}).get("fast_ema_period", 20))

    @property
    def slow_ema(self) -> int:
        return int(self.commands.get("advanced_strategy", {}).get("slow_ema_period", 50))

    @property
    def use_h1_trend_filter(self) -> bool:
        return bool(self.commands.get("advanced_strategy", {}).get("use_h1_trend_filter", True))

    @property
    def h1_trend_fast_ema(self) -> int:
        return int(self.commands.get("advanced_strategy", {}).get("h1_trend_ema_fast", 50))

    @property
    def h1_trend_slow_ema(self) -> int:
        return int(self.commands.get("advanced_strategy", {}).get("h1_trend_ema_slow", 200))

    @property
    def rsi_period(self) -> int:
        strat = self.commands.get("advanced_strategy", self.commands.get("strategy_settings", {}))
        return int(strat.get("rsi_period", 14))

    @property
    def rsi_buy_range(self) -> Tuple[float, float]:
        cfg = self.commands.get("advanced_strategy", self.commands.get("strategy_settings", {}))
        return float(cfg.get("rsi_buy_pullback_min", 38.0)), float(cfg.get("rsi_buy_pullback_max", 54.0))

    @property
    def rsi_sell_range(self) -> Tuple[float, float]:
        cfg = self.commands.get("advanced_strategy", self.commands.get("strategy_settings", {}))
        return float(cfg.get("rsi_sell_pullback_min", 46.0)), float(cfg.get("rsi_sell_pullback_max", 62.0))

    @property
    def atr_period(self) -> int:
        return int(self.commands.get("advanced_strategy", {}).get("atr_period", 14))

    # --- Profit Protection (Break-Even & Trailing Stop) ---
    @property
    def use_break_even(self) -> bool:
        return bool(self.commands.get("profit_protection_and_trailing", {}).get("use_break_even", True))

    @property
    def gold_be_trigger(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("gold_break_even_trigger_usd", 2.50))

    @property
    def gold_be_lock(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("gold_break_even_lock_usd", 0.50))

    @property
    def forex_be_trigger(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("forex_break_even_trigger_pips", 15.0))

    @property
    def forex_be_lock(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("forex_break_even_lock_pips", 2.0))

    @property
    def use_trailing_stop(self) -> bool:
        return bool(self.commands.get("profit_protection_and_trailing", {}).get("use_trailing_stop", True))

    @property
    def gold_trailing_trigger(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("gold_trailing_trigger_usd", 4.50))

    @property
    def gold_trailing_dist(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("gold_trailing_distance_usd", 2.00))

    @property
    def forex_trailing_trigger(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("forex_trailing_trigger_pips", 25.0))

    @property
    def forex_trailing_dist(self) -> float:
        return float(self.commands.get("profit_protection_and_trailing", {}).get("forex_trailing_distance_pips", 12.0))

    # --- Filters ---
    @property
    def active_sessions_only(self) -> bool:
        return bool(self.commands.get("filters", {}).get("active_sessions_only", True))

    @property
    def session_start_utc(self) -> int:
        return int(self.commands.get("filters", {}).get("allowed_session_start_utc_hour", 7))

    @property
    def session_end_utc(self) -> int:
        return int(self.commands.get("filters", {}).get("allowed_session_end_utc_hour", 20))

    @property
    def max_spread_gold(self) -> float:
        return float(self.commands.get("filters", {}).get("max_allowed_spread_gold_usd", 0.45))

    @property
    def max_spread_forex(self) -> float:
        return float(self.commands.get("filters", {}).get("max_allowed_spread_pips_forex", 2.0))

    # --- H4 S&R Engulfing Strategy Settings ---
    @property
    def h4_snr_enabled(self) -> bool:
        return bool(self.commands.get("h4_snr_engulfing_strategy", {}).get("enabled", True))

    @property
    def h4_entry_timeframe(self) -> int:
        tf_str = self.commands.get("h4_snr_engulfing_strategy", {}).get("entry_timeframe", "M5").upper()
        return self.TIMEFRAME_MAP.get(tf_str, mt5.TIMEFRAME_M5)

    @property
    def h4_lookback(self) -> int:
        return int(self.commands.get("h4_snr_engulfing_strategy", {}).get("h4_lookback_candles", 40))

    @property
    def h4_tolerance_pct(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("support_resistance_tolerance_pct", 0.25))

    @property
    def h4_sl_mode(self) -> str:
        return self.commands.get("h4_snr_engulfing_strategy", {}).get("sl_calculation_mode", "DYNAMIC_MARKET_STRUCTURE").upper()

    @property
    def risk_reward_ratio(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("risk_reward_ratio", 2.0))

    @property
    def structure_sl_buffer_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("structure_sl_buffer_pips", 2.5))

    @property
    def structure_sl_buffer_gold_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("structure_sl_buffer_gold_usd", 0.60))

    @property
    def gold_min_sl_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_min_sl_usd", 2.0))

    @property
    def gold_max_sl_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_max_sl_usd", 6.0))

    @property
    def forex_min_sl_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_min_sl_pips", 12.0))

    @property
    def forex_max_sl_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_max_sl_pips", 35.0))

    @property
    def gold_fallback_sl_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_fallback_sl_usd", 3.5))

    @property
    def forex_fallback_sl_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_fallback_sl_pips", 20.0))


cmd_manager = CommandManager()


# =============================================================================
# EXNESS SYMBOL DISCOVERY
# =============================================================================
class SymbolManager:
    """Discovers exact symbol names used by Exness (e.g. XAUUSDm, EURUSDm)."""

    def __init__(self):
        self.symbol_map: Dict[str, str] = {}

    def discover_symbols(self, target_pairs: List[str]) -> Dict[str, str]:
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            logger.error("Could not fetch symbol list from MT5.")
            return {}

        available_names = {s.name for s in all_symbols}

        for base in target_pairs:
            candidates = [
                base,
                f"{base}m",
                f"{base}.m",
                f"{base}_i",
                f"{base}c",
                f"{base}+",
            ]
            found = None
            for c in candidates:
                if c in available_names:
                    found = c
                    break

            if not found:
                for name in available_names:
                    if base in name and not name.endswith(("_i", "_test")):
                        found = name
                        break

            if found:
                mt5.symbol_select(found, True)
                self.symbol_map[base] = found
                logger.info(f"  [Symbol Map] {base} -> Matched Exness Symbol: '{found}'")
            else:
                logger.warning(f"  [Symbol Map] Could not find matching symbol for {base}")

        return self.symbol_map


# =============================================================================
# TECHNICAL STRATEGY ENGINE
# =============================================================================
class StrategyEngine:
    """Evaluates market data using institutional rules from CommandManager."""

    @staticmethod
    def get_candles(symbol: str, timeframe: int, count: int = 150) -> Optional[pd.DataFrame]:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df["ema_fast"] = df["close"].ewm(span=cmd_manager.fast_ema, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=cmd_manager.slow_ema, adjust=False).mean()

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=cmd_manager.rsi_period, min_periods=cmd_manager.rsi_period).mean()
        avg_loss = loss.rolling(window=cmd_manager.rsi_period, min_periods=cmd_manager.rsi_period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        df["rsi"] = 100 - (100 / (1 + rs))

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=cmd_manager.atr_period).mean()

        return df

    @classmethod
    def get_h4_support_resistance(cls, symbol: str, lookback: int = 40) -> Tuple[List[float], List[float]]:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, lookback)
        if rates is None or len(rates) < 10:
            return [], []

        df = pd.DataFrame(rates)
        supports = []
        resistances = []

        for i in range(2, len(df) - 2):
            if df["high"].iloc[i] > df["high"].iloc[i-1] and df["high"].iloc[i] > df["high"].iloc[i-2] and \
               df["high"].iloc[i] > df["high"].iloc[i+1] and df["high"].iloc[i] > df["high"].iloc[i+2]:
                resistances.append(float(df["high"].iloc[i]))

            if df["low"].iloc[i] < df["low"].iloc[i-1] and df["low"].iloc[i] < df["low"].iloc[i-2] and \
               df["low"].iloc[i] < df["low"].iloc[i+1] and df["low"].iloc[i] < df["low"].iloc[i+2]:
                supports.append(float(df["low"].iloc[i]))

        supports.append(float(df["low"].min()))
        resistances.append(float(df["high"].max()))

        return sorted(list(set(supports))), sorted(list(set(resistances)))

    @staticmethod
    def detect_engulfing(df: pd.DataFrame) -> Tuple[bool, bool]:
        if len(df) < 3:
            return False, False

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        is_bullish = (prev["close"] < prev["open"]) and \
                     (curr["close"] > curr["open"]) and \
                     (curr["open"] <= prev["close"] * 1.0005) and \
                     (curr["close"] >= prev["open"] * 0.9995)

        is_bearish = (prev["close"] > prev["open"]) and \
                     (curr["close"] < curr["open"]) and \
                     (curr["open"] >= prev["close"] * 0.9995) and \
                     (curr["close"] <= prev["open"] * 1.0005)

        return is_bullish, is_bearish

    @classmethod
    def evaluate(cls, symbol: str) -> Tuple[str, str, float, str, Dict[str, Any]]:
        # 1. Strategy 1: H4 Support/Resistance + M15/M5 Engulfing Strategy
        if cmd_manager.h4_snr_enabled:
            supports, resistances = cls.get_h4_support_resistance(symbol, cmd_manager.h4_lookback)
            tick = mt5.symbol_info_tick(symbol)
            cur_price = tick.bid if tick else 0.0

            if cur_price > 0 and (supports or resistances):
                tol = cmd_manager.h4_tolerance_pct / 100.0

                near_support = None
                for s in supports:
                    if abs(cur_price - s) / cur_price <= tol:
                        near_support = s
                        break

                near_resistance = None
                for r in resistances:
                    if abs(cur_price - r) / cur_price <= tol:
                        near_resistance = r
                        break

                entry_df = cls.get_candles(symbol, cmd_manager.h4_entry_timeframe, 30)
                if entry_df is not None and len(entry_df) >= 3:
                    is_bull_engulf, is_bear_engulf = cls.detect_engulfing(entry_df)

                    if near_support and is_bull_engulf:
                        if cmd_manager.trading_side in ("BOTH", "BUY_ONLY"):
                            pat_low = float(min(entry_df["low"].iloc[-1], entry_df["low"].iloc[-2]))
                            inval = min(pat_low, near_support)
                            struct_meta = {
                                "invalidation_price": inval,
                                "support": near_support,
                                "pattern_low": pat_low
                            }
                            reason = f"H4 Support Zone ({near_support:.2f}) + Bullish Engulfing (Low: {pat_low:.2f})! 1:2 R:R"
                            return "BUY", reason, 0.0, "H4_SNR", struct_meta

                    if near_resistance and is_bear_engulf:
                        if cmd_manager.trading_side in ("BOTH", "SELL_ONLY"):
                            pat_high = float(max(entry_df["high"].iloc[-1], entry_df["high"].iloc[-2]))
                            inval = max(pat_high, near_resistance)
                            struct_meta = {
                                "invalidation_price": inval,
                                "resistance": near_resistance,
                                "pattern_high": pat_high
                            }
                            reason = f"H4 Resistance Zone ({near_resistance:.2f}) + Bearish Engulfing (High: {pat_high:.2f})! 1:2 R:R"
                            return "SELL", reason, 0.0, "H4_SNR", struct_meta

        # 2. Strategy 2: Institutional H1 Trend Bias + M5 Value Pullback
        df = cls.get_candles(symbol, cmd_manager.timeframe, 150)
        if df is None or len(df) < 60:
            return "HOLD", "Insufficient candle data", 0.0, "NONE", {}

        df = cls.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        cur_price = last["close"]
        ema_fast = last["ema_fast"]
        ema_slow = last["ema_slow"]
        rsi = last["rsi"]
        atr = last["atr"] if not math.isnan(last["atr"]) else 0.0

        if math.isnan(ema_fast) or math.isnan(ema_slow) or math.isnan(rsi) or atr == 0.0:
            return "HOLD", "Indicators initializing", 0.0, "NONE", {}

        # Higher Timeframe (H1) Trend Anchor
        h1_bullish = True
        h1_bearish = True
        if cmd_manager.use_h1_trend_filter:
            h1_df = cls.get_candles(symbol, mt5.TIMEFRAME_H1, 220)
            if h1_df is not None and len(h1_df) >= 200:
                h1_fast = h1_df["close"].ewm(span=cmd_manager.h1_trend_fast_ema, adjust=False).mean().iloc[-1]
                h1_slow = h1_df["close"].ewm(span=cmd_manager.h1_trend_slow_ema, adjust=False).mean().iloc[-1]
                h1_close = h1_df["close"].iloc[-1]
                h1_bullish = (h1_close > h1_fast) and (h1_fast > h1_slow)
                h1_bearish = (h1_close < h1_fast) and (h1_fast < h1_slow)

        # M5 Value Pullback & Rejection Confirmation
        candle_bullish = (last["close"] > last["open"])
        candle_bearish = (last["close"] < last["open"])

        rsi_buy_min, rsi_buy_max = cmd_manager.rsi_buy_range
        rsi_sell_min, rsi_sell_max = cmd_manager.rsi_sell_range

        # BUY PULLBACK: H1 Bullish + M5 fast > slow + Low touched EMA + RSI in discount + Bullish Rejection
        buy_pullback = h1_bullish and (ema_fast > ema_slow) and \
                       (last["low"] <= ema_fast * 1.0015) and \
                       (rsi_buy_min <= rsi <= rsi_buy_max) and candle_bullish

        # SELL PULLBACK: H1 Bearish + M5 fast < slow + High touched EMA + RSI in premium + Bearish Rejection
        sell_pullback = h1_bearish and (ema_fast < ema_slow) and \
                        (last["high"] >= ema_fast * 0.9985) and \
                        (rsi_sell_min <= rsi <= rsi_sell_max) and candle_bearish

        if buy_pullback:
            if cmd_manager.trading_side in ("BOTH", "BUY_ONLY"):
                reason = f"Institutional H1 Bullish + M5 Pullback into EMA{cmd_manager.fast_ema} ({ema_fast:.2f}) + RSI Discount ({rsi:.1f}) + Green Rejection"
                return "BUY", reason, atr, "INST_TREND", {}

        if sell_pullback:
            if cmd_manager.trading_side in ("BOTH", "SELL_ONLY"):
                reason = f"Institutional H1 Bearish + M5 Rally into EMA{cmd_manager.fast_ema} ({ema_fast:.2f}) + RSI Premium ({rsi:.1f}) + Red Rejection"
                return "SELL", reason, atr, "INST_TREND", {}

        return "HOLD", f"Neutral. H1 Bullish={h1_bullish}, RSI={rsi:.1f}, EMA_Fast={ema_fast:.2f}", atr, "NONE", {}


# =============================================================================
# ORDER EXECUTOR & RISK CONTROLLER
# =============================================================================
class OrderExecutor:
    """Safely executes orders in MT5 according to rules in CommandManager."""

    MAGIC_NUMBER = 998877

    @classmethod
    def get_open_positions(cls, symbol: Optional[str] = None) -> list:
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []
        return [p for p in positions if p.magic == cls.MAGIC_NUMBER or p.magic == 0]

    @classmethod
    def calculate_lot_size(cls, symbol: str, stop_loss_distance: float) -> float:
        info = mt5.symbol_info(symbol)
        min_lot = max(info.volume_min if info else 0.01, cmd_manager.min_lot_limit)
        max_lot = min(info.volume_max if info else 10.0, cmd_manager.max_lot_limit)
        step = info.volume_step if info else 0.01

        if cmd_manager.use_fixed_lot:
            lot = cmd_manager.lot_size
            return round(max(min_lot, min(lot, max_lot)), 2)

        account = mt5.account_info()
        if not account or stop_loss_distance <= 0 or not info:
            return min_lot

        risk_amount = account.equity * (cmd_manager.risk_percent / 100.0)
        tick_value = info.trade_tick_value
        tick_size = info.trade_tick_size

        if tick_value > 0 and tick_size > 0:
            loss_per_lot = (stop_loss_distance / tick_size) * tick_value
            if loss_per_lot > 0:
                raw_volume = risk_amount / loss_per_lot
                lots = math.floor(raw_volume / step) * step
                calculated_lot = round(max(min_lot, min(lots, max_lot)), 2)
                logger.info(f"  [Risk Sizing] Equity: ${account.equity:.2f} | Risk: {cmd_manager.risk_percent}% (${risk_amount:.2f}) | Market SL Dist: {stop_loss_distance:.4f} -> Calculated Lot: {calculated_lot}")
                return calculated_lot

        return min_lot

    @classmethod
    def is_market_open(cls, symbol: str) -> bool:
        info = mt5.symbol_info(symbol)
        if not info or info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            return False

        is_crypto = any(c in symbol.upper() for c in ["BTC", "ETH", "LTC", "XRP", "SOL"])
        if is_crypto:
            return True

        now_utc = datetime.now(timezone.utc)
        weekday = now_utc.weekday()
        if weekday == 5:
            return False
        if weekday == 6 and now_utc.hour < 22:
            return False
        if weekday == 4 and now_utc.hour >= 22:
            return False

        return True

    @classmethod
    def check_spread_allowed(cls, symbol: str) -> bool:
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            return False

        is_gold = "XAU" in symbol.upper()
        if is_gold:
            spread_usd = tick.ask - tick.bid
            if spread_usd > cmd_manager.max_spread_gold:
                logger.warning(f"Spread on Gold {symbol} is ${spread_usd:.3f} (Limit: ${cmd_manager.max_spread_gold:.2f}). Skipping.")
                return False
        else:
            spread_pips = (tick.ask - tick.bid) / (info.point * 10)
            if spread_pips > cmd_manager.max_spread_forex:
                logger.warning(f"Spread on {symbol} is {spread_pips:.1f} pips (Limit: {cmd_manager.max_spread_forex:.1f}). Skipping.")
                return False
        return True

    @classmethod
    def open_trade(cls, symbol: str, side: str, atr: float, reason: str, strategy_type: str = "INST_TREND", struct_info: Optional[Dict[str, Any]] = None) -> bool:
        if not cls.check_spread_allowed(symbol):
            return False

        info = mt5.symbol_info(symbol)
        if not info:
            return False

        if not info.visible:
            mt5.symbol_select(symbol, True)

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False

        stop_level_pts = (int)(getattr(info, "trade_stops_level", 0) or 0)
        min_stop_dist = max(stop_level_pts * info.point, (tick.ask - tick.bid) * 2.0)
        is_gold = "XAU" in symbol.upper()
        digits = info.digits
        point = info.point

        # Calculate Dynamic Stop Loss & Take Profit according to Market Structure & 1:2 R:R
        if strategy_type == "H4_SNR" and struct_info and cmd_manager.h4_sl_mode == "DYNAMIC_MARKET_STRUCTURE":
            inval = struct_info.get("invalidation_price")
            if side == "BUY":
                buffer = cmd_manager.structure_sl_buffer_gold_usd if is_gold else (cmd_manager.structure_sl_buffer_pips * point * 10)
                target_sl = (inval - buffer) if inval else (tick.ask - (cmd_manager.gold_fallback_sl_usd if is_gold else cmd_manager.forex_fallback_sl_pips * point * 10))
                sl_distance = tick.ask - target_sl
                if is_gold:
                    sl_distance = max(cmd_manager.gold_min_sl_usd, min(sl_distance, cmd_manager.gold_max_sl_usd))
                else:
                    sl_distance = max(cmd_manager.forex_min_sl_pips * point * 10, min(sl_distance, cmd_manager.forex_max_sl_pips * point * 10))
                sl_distance = max(sl_distance, min_stop_dist)
                tp_distance = sl_distance * cmd_manager.risk_reward_ratio

                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                sl = round(price - sl_distance, digits)
                tp = round(price + tp_distance, digits)
            else:  # SELL
                buffer = cmd_manager.structure_sl_buffer_gold_usd if is_gold else (cmd_manager.structure_sl_buffer_pips * point * 10)
                target_sl = (inval + buffer) if inval else (tick.bid + (cmd_manager.gold_fallback_sl_usd if is_gold else cmd_manager.forex_fallback_sl_pips * point * 10))
                sl_distance = target_sl - tick.bid
                if is_gold:
                    sl_distance = max(cmd_manager.gold_min_sl_usd, min(sl_distance, cmd_manager.gold_max_sl_usd))
                else:
                    sl_distance = max(cmd_manager.forex_min_sl_pips * point * 10, min(sl_distance, cmd_manager.forex_max_sl_pips * point * 10))
                sl_distance = max(sl_distance, min_stop_dist)
                tp_distance = sl_distance * cmd_manager.risk_reward_ratio

                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                sl = round(price + sl_distance, digits)
                tp = round(price - tp_distance, digits)
        else:
            # Institutional Trend Pullback (1.8 ATR with sanity bounds, 1:2 R:R)
            sl_distance = max(atr * 1.8, min_stop_dist)
            if is_gold:
                sl_distance = max(cmd_manager.gold_min_sl_usd, min(sl_distance, cmd_manager.gold_max_sl_usd))
            else:
                sl_distance = max(cmd_manager.forex_min_sl_pips * point * 10, min(sl_distance, cmd_manager.forex_max_sl_pips * point * 10))

            tp_distance = sl_distance * 2.0  # Strict 1:2 Risk to Reward
            if side == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                sl = round(price - sl_distance, digits)
                tp = round(price + tp_distance, digits)
            else:
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                sl = round(price + sl_distance, digits)
                tp = round(price - tp_distance, digits)

        volume = cls.calculate_lot_size(symbol, sl_distance)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 25,
            "magic": cls.MAGIC_NUMBER,
            "comment": "ExnessInstBot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        filling_mode = info.filling_mode
        if filling_mode & 1:
            request["type_filling"] = mt5.ORDER_FILLING_FOK
        elif filling_mode & 2:
            request["type_filling"] = mt5.ORDER_FILLING_IOC
        else:
            request["type_filling"] = mt5.ORDER_FILLING_RETURN

        logger.info(f"==> SENDING {side} ORDER: {symbol} | Volume: {volume} | Price: {price} | SL: {sl} | TP: {tp}")
        logger.info(f"    Reason: {reason}")

        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code = result.retcode if result else mt5.last_error()
            logger.error(f"❌ Order failed! Code: {error_code} | Comment: {result.comment if result else ''}")
            return False

        logger.info(f"✅ [ORDER EXECUTED] Deal Ticket: #{result.deal} | Order Ticket: #{result.order} | Price: {result.price}")
        return True

    @classmethod
    def manage_profit_protection_and_trailing(cls, symbol: str):
        """
        Symbol-aware Profit Protection:
        1. Break-Even: Locks in risk-free trade at 1R profit (+0.50 USD on Gold / +2 pips on Forex).
        2. Breathing Trailing Stop: Only activates at $4.50+ on Gold, trailing $2.00 behind price.
        """
        positions = cls.get_open_positions(symbol)
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not positions or not tick:
            return

        is_gold = "XAU" in symbol.upper()
        digits = info.digits
        point = info.point

        be_trigger = cmd_manager.gold_be_trigger if is_gold else (cmd_manager.forex_be_trigger * point * 10)
        be_lock = cmd_manager.gold_be_lock if is_gold else (cmd_manager.forex_be_lock * point * 10)
        trail_trigger = cmd_manager.gold_trailing_trigger if is_gold else (cmd_manager.forex_trailing_trigger * point * 10)
        trail_dist = cmd_manager.gold_trailing_dist if is_gold else (cmd_manager.forex_trailing_dist * point * 10)

        for pos in positions:
            if pos.type == mt5.ORDER_TYPE_BUY:
                profit_dist = tick.bid - pos.price_open

                # 1. Break-Even
                if cmd_manager.use_break_even and profit_dist >= be_trigger:
                    be_sl = round(pos.price_open + be_lock, digits)
                    if pos.sl < be_sl:
                        logger.info(f"🛡️ [BREAK-EVEN ACTIVATED] BUY #{pos.ticket} SL moved to {be_sl} (Locked +${round(be_lock, 2)}, 100% Risk Free!)")
                        cls._modify_position_sl(pos.ticket, be_sl, pos.tp)

                # 2. Breathing Trailing Stop
                if cmd_manager.use_trailing_stop and profit_dist >= trail_trigger:
                    new_sl = round(tick.bid - trail_dist, digits)
                    if new_sl > pos.sl and new_sl > pos.price_open:
                        logger.info(f"📈 [TRAILING STOP] BUY #{pos.ticket} SL moved to {new_sl} (Locked Profit: +${round(new_sl - pos.price_open, 2)})")
                        cls._modify_position_sl(pos.ticket, new_sl, pos.tp)

            elif pos.type == mt5.ORDER_TYPE_SELL:
                profit_dist = pos.price_open - tick.ask

                # 1. Break-Even
                if cmd_manager.use_break_even and profit_dist >= be_trigger:
                    be_sl = round(pos.price_open - be_lock, digits)
                    if pos.sl == 0.0 or pos.sl > be_sl:
                        logger.info(f"🛡️ [BREAK-EVEN ACTIVATED] SELL #{pos.ticket} SL moved to {be_sl} (Locked +${round(be_lock, 2)}, 100% Risk Free!)")
                        cls._modify_position_sl(pos.ticket, be_sl, pos.tp)

                # 2. Breathing Trailing Stop
                if cmd_manager.use_trailing_stop and profit_dist >= trail_trigger:
                    new_sl = round(tick.ask + trail_dist, digits)
                    if (pos.sl == 0.0 or new_sl < pos.sl) and new_sl < pos.price_open:
                        logger.info(f"📉 [TRAILING STOP] SELL #{pos.ticket} SL moved to {new_sl} (Locked Profit: +${round(pos.price_open - new_sl, 2)})")
                        cls._modify_position_sl(pos.ticket, new_sl, pos.tp)

    @staticmethod
    def _modify_position_sl(ticket: int, new_sl: float, tp: float):
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": tp,
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"  SL successfully modified on ticket #{ticket} to {new_sl}")


# =============================================================================
# MAIN AUTOTRADER CONTROLLER
# =============================================================================
class ExnessAutoBot:
    """The central trading loop that executes instructions from bot_commands.json."""

    def __init__(self):
        self.symbol_manager = SymbolManager()
        self.active_symbols: Dict[str, str] = {}
        self.last_trade_times: Dict[str, float] = {}
        self.is_running = False

    def initialize(self) -> bool:
        logger.info("=" * 65)
        logger.info("   EXNESS MT5 DIRECT AUTO-TRADING BOT v2.0")
        logger.info("=" * 65)

        logger.info("Connecting to MetaTrader 5...")
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed! Error code: {mt5.last_error()}")
            return False

        account = mt5.account_info()
        if not account:
            logger.error("Could not retrieve MT5 account info.")
            return False

        terminal = mt5.terminal_info()

        logger.info(f"✅ CONNECTED TO EXNESS MT5")
        logger.info(f"   Account Number: {account.login}")
        logger.info(f"   Server        : {account.server}")
        logger.info(f"   Account Name  : {account.name}")
        logger.info(f"   Balance       : ${account.balance:.2f} {account.currency}")
        logger.info(f"   Equity        : ${account.equity:.2f} {account.currency}")
        logger.info(f"   Leverage      : 1:{account.leverage}")
        logger.info(f"   Algo Trading  : {'ENABLED' if terminal.trade_allowed else 'DISABLED ⚠️'}")
        logger.info("-" * 65)

        self.active_symbols = self.symbol_manager.discover_symbols(cmd_manager.active_symbols)
        if not self.active_symbols:
            logger.error("No trading symbols matched. Exiting.")
            return False

        return True

    def get_today_trades_count(self) -> int:
        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)
        deals = mt5.history_deals_get(start_of_day, now)
        if not deals:
            return 0
        return sum(1 for d in deals if d.entry == 1 and d.magic == OrderExecutor.MAGIC_NUMBER)

    def run(self):
        self.is_running = True
        logger.info("🚀 BOT IS RUNNING. Live listening to bot_commands.json...")
        logger.info(f"Active Pairs: {list(self.active_symbols.keys())} | Lot: {cmd_manager.lot_size}")
        logger.info("=" * 65)

        try:
            while self.is_running:
                # 1. Hot-reload bot_commands.json
                if cmd_manager.load():
                    self.active_symbols = self.symbol_manager.discover_symbols(cmd_manager.active_symbols)

                account = mt5.account_info()
                if not account:
                    time.sleep(5)
                    continue

                total_open = len(OrderExecutor.get_open_positions())

                # Session Filter Check (London & New York Sessions)
                if cmd_manager.active_sessions_only:
                    now_utc = datetime.now(timezone.utc)
                    if now_utc.hour < cmd_manager.session_start_utc or now_utc.hour >= cmd_manager.session_end_utc:
                        time.sleep(cmd_manager.check_interval)
                        continue

                # Daily Trades Limit (Anti-Overtrading)
                today_trades = self.get_today_trades_count()
                if today_trades >= cmd_manager.max_daily_trades:
                    time.sleep(cmd_manager.check_interval)
                    continue

                for base_name, actual_symbol in self.active_symbols.items():
                    # 1. Always manage Profit Protection & Breathing Trailing
                    OrderExecutor.manage_profit_protection_and_trailing(actual_symbol)

                    # Market open check
                    if not OrderExecutor.is_market_open(actual_symbol):
                        continue

                    # Pause check
                    if cmd_manager.pause_trading:
                        continue

                    # Cooldown check
                    last_time = self.last_trade_times.get(actual_symbol, 0)
                    if time.time() - last_time < cmd_manager.trade_cooldown_minutes * 60:
                        continue

                    # Max open positions check
                    symbol_positions = OrderExecutor.get_open_positions(actual_symbol)
                    if len(symbol_positions) >= cmd_manager.max_open_per_pair:
                        continue

                    if total_open >= cmd_manager.max_total_open:
                        continue

                    # Evaluate Strategy Signals
                    signal, reason, atr, strat_type, struct_info = StrategyEngine.evaluate(actual_symbol)

                    tick = mt5.symbol_info_tick(actual_symbol)
                    bid_price = tick.bid if tick else 0.0

                    now_str = datetime.now().strftime("%H:%M:%S")
                    if signal in ("BUY", "SELL"):
                        logger.info(f"[{now_str}] 🎯 SIGNAL: {base_name} ({actual_symbol}) -> {signal} | Strategy: {strat_type} | Rate: {bid_price:.2f}")
                        logger.info(f"         Reason: {reason}")
                        success = OrderExecutor.open_trade(actual_symbol, signal, atr, reason, strategy_type=strat_type, struct_info=struct_info)
                        if success:
                            self.last_trade_times[actual_symbol] = time.time()

                time.sleep(cmd_manager.check_interval)

        except KeyboardInterrupt:
            logger.info("\n[STOPPED] Bot was stopped by user (Ctrl+C). Active trades in MT5 remain safe.")
        finally:
            mt5.shutdown()
            logger.info("MT5 connection closed.")


if __name__ == "__main__":
    bot = ExnessAutoBot()
    if bot.initialize():
        bot.run()
