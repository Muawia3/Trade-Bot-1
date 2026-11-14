"""
=============================================================================
         EXNESS MT5 DIRECT AUTO-TRADING BOT (XAU/USD & EUR/USD)
=============================================================================
Features:
- Dynamic Command & Rules Hot-Reloading from bot_commands.json
- Direct execution in MetaTrader 5 (Exness)
- EMA Cascades, RSI Momentum, ATR Dynamic SL/TP & Trailing Stop
- Auto-discovery of Exness symbols (XAUUSDm, EURUSDm, etc.)
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
                strat = self.commands.get("strategy_settings", {})

                if not initial:
                    logger.info("=" * 65)
                    logger.info("🔄 [COMMANDS UPDATED] Loaded new instructions from bot_commands.json:")
                    logger.info(f"   Active Pairs : {gen.get('active_symbols', ['XAUUSD', 'EURUSD'])}")
                    logger.info(f"   Trading Side : {gen.get('trading_side', 'BOTH')}")
                    logger.info(f"   Lot Size     : {risk.get('lot_size', 0.01)}")
                    logger.info(f"   Timeframe    : {strat.get('timeframe', 'M5')}")
                    logger.info(f"   Paused       : {gen.get('pause_trading', False)}")
                    logger.info("=" * 65)
                return True
        except Exception as e:
            logger.error(f"Failed to read commands file {self.filepath}: {e}")
        return False

    # --- Convenient Property Accessors ---
    @property
    def pause_trading(self) -> bool:
        return self.commands.get("general", {}).get("pause_trading", False)

    @property
    def trading_side(self) -> str:
        return self.commands.get("general", {}).get("trading_side", "BOTH").upper()

    @property
    def active_symbols(self) -> List[str]:
        return self.commands.get("general", {}).get("active_symbols", ["XAUUSD", "EURUSD"])

    @property
    def check_interval(self) -> int:
        return int(self.commands.get("general", {}).get("check_interval_seconds", 10))

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
    def max_daily_loss(self) -> float:
        return float(self.commands.get("money_and_risk", {}).get("max_daily_loss_usd", 50.0))

    @property
    def timeframe(self) -> int:
        tf_str = self.commands.get("strategy_settings", {}).get("timeframe", "M5").upper()
        return self.TIMEFRAME_MAP.get(tf_str, mt5.TIMEFRAME_M5)

    @property
    def fast_ema(self) -> int:
        return int(self.commands.get("strategy_settings", {}).get("fast_ema_period", 20))

    @property
    def slow_ema(self) -> int:
        return int(self.commands.get("strategy_settings", {}).get("slow_ema_period", 50))

    @property
    def trend_ema(self) -> int:
        return int(self.commands.get("strategy_settings", {}).get("trend_ema_period", 200))

    @property
    def rsi_period(self) -> int:
        return int(self.commands.get("strategy_settings", {}).get("rsi_period", 14))

    @property
    def rsi_buy_range(self) -> Tuple[float, float]:
        cfg = self.commands.get("strategy_settings", {})
        return float(cfg.get("rsi_buy_min", 45.0)), float(cfg.get("rsi_buy_max", 68.0))

    @property
    def rsi_sell_range(self) -> Tuple[float, float]:
        cfg = self.commands.get("strategy_settings", {})
        return float(cfg.get("rsi_sell_min", 32.0)), float(cfg.get("rsi_sell_max", 55.0))

    @property
    def require_trend_ema(self) -> bool:
        return bool(self.commands.get("strategy_settings", {}).get("require_trend_ema_filter", True))

    @property
    def atr_period(self) -> int:
        return int(self.commands.get("stop_loss_and_take_profit", {}).get("atr_period", 14))

    @property
    def sl_atr_multiplier(self) -> float:
        return float(self.commands.get("stop_loss_and_take_profit", {}).get("stop_loss_atr_multiplier", 1.5))

    @property
    def tp_atr_multiplier(self) -> float:
        return float(self.commands.get("stop_loss_and_take_profit", {}).get("take_profit_atr_multiplier", 3.0))

    @property
    def use_trailing_stop(self) -> bool:
        return bool(self.commands.get("stop_loss_and_take_profit", {}).get("use_trailing_stop", True))

    @property
    def trailing_start_pips(self) -> float:
        return float(self.commands.get("stop_loss_and_take_profit", {}).get("trailing_activation_pips", 15.0))

    @property
    def trailing_step_pips(self) -> float:
        return float(self.commands.get("stop_loss_and_take_profit", {}).get("trailing_step_pips", 5.0))

    @property
    def max_spread_gold(self) -> float:
        return float(self.commands.get("advanced_filters", {}).get("max_allowed_spread_pips_gold", 6.0))

    @property
    def max_spread_forex(self) -> float:
        return float(self.commands.get("advanced_filters", {}).get("max_allowed_spread_pips_forex", 3.0))

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
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("structure_sl_buffer_pips", 2.0))

    @property
    def structure_sl_buffer_gold_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("structure_sl_buffer_gold_usd", 0.50))

    @property
    def gold_min_sl_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_min_sl_usd", 1.5))

    @property
    def gold_max_sl_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_max_sl_usd", 8.0))

    @property
    def forex_min_sl_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_min_sl_pips", 10.0))

    @property
    def forex_max_sl_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_max_sl_pips", 45.0))

    @property
    def gold_sl_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("fallback_fixed_gold_sl_usd", self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_sl_usd", 4.0)))

    @property
    def gold_tp_usd(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("fallback_fixed_gold_tp_usd", self.commands.get("h4_snr_engulfing_strategy", {}).get("gold_tp_usd", 8.0)))

    @property
    def forex_sl_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("fallback_fixed_forex_sl_pips", self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_sl_pips", 20.0)))

    @property
    def forex_tp_pips(self) -> float:
        return float(self.commands.get("h4_snr_engulfing_strategy", {}).get("fallback_fixed_forex_tp_pips", self.commands.get("h4_snr_engulfing_strategy", {}).get("forex_tp_pips", 40.0)))


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
            logger.error("Could not fetch symbols from MT5 terminal.")
            return {}

        available_names = {s.name for s in all_symbols}
        self.symbol_map.clear()

        for base in target_pairs:
            candidates = [
                base,
                f"{base}m",       # Exness Standard
                f"{base}c",       # Exness Cent
                f"{base}r",       # Exness Raw Spread
                f"{base}z",       # Exness Zero
                f"{base}.a",
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
    """Evaluates market data using rules from CommandManager."""

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
        df["ema_trend"] = df["close"].ewm(span=cmd_manager.trend_ema, adjust=False).mean()

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
        """Identify key H4 Support and Resistance levels from swing points."""
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
        """Detect Bullish or Bearish Engulfing pattern on the last 2 completed candles."""
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
        # 1. Check H4 Support/Resistance + M15/M5 Engulfing Strategy
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
                            reason = f"H4 Support Zone ({near_support:.2f}) + Bullish Engulfing (Low: {pat_low:.2f})! Dynamic Market SL & 1:{cmd_manager.risk_reward_ratio:.1f} R:R"
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
                            reason = f"H4 Resistance Zone ({near_resistance:.2f}) + Bearish Engulfing (High: {pat_high:.2f})! Dynamic Market SL & 1:{cmd_manager.risk_reward_ratio:.1f} R:R"
                            return "SELL", reason, 0.0, "H4_SNR", struct_meta

        # 2. Regular EMA Cascade + RSI Strategy
        df = cls.get_candles(symbol, cmd_manager.timeframe, 150)
        if df is None or len(df) < 60:
            return "HOLD", "Insufficient candle data", 0.0, "NONE", {}

        df = cls.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        cur_price = last["close"]
        ema_fast = last["ema_fast"]
        ema_slow = last["ema_slow"]
        ema_trend = last["ema_trend"]
        rsi = last["rsi"]
        atr = last["atr"] if not math.isnan(last["atr"]) else 0.0

        if math.isnan(ema_fast) or math.isnan(ema_slow) or math.isnan(rsi) or atr == 0.0:
            return "HOLD", "Indicators initializing", 0.0, "NONE", {}

        rsi_buy_min, rsi_buy_max = cmd_manager.rsi_buy_range
        rsi_sell_min, rsi_sell_max = cmd_manager.rsi_sell_range

        # BUY CONDITION
        buy_trend = ema_fast > ema_slow and cur_price > ema_fast
        if cmd_manager.require_trend_ema:
            buy_trend = buy_trend and cur_price > ema_trend

        if buy_trend and (rsi_buy_min <= rsi <= rsi_buy_max):
            if cmd_manager.trading_side in ("BOTH", "BUY_ONLY"):
                reason = f"Uptrend (EMA{cmd_manager.fast_ema}={ema_fast:.2f} > EMA{cmd_manager.slow_ema}={ema_slow:.2f}), RSI={rsi:.1f} Bullish"
                return "BUY", reason, atr, "EMA_RSI", {}

        # SELL CONDITION
        sell_trend = ema_fast < ema_slow and cur_price < ema_fast
        if cmd_manager.require_trend_ema:
            sell_trend = sell_trend and cur_price < ema_trend

        if sell_trend and (rsi_sell_min <= rsi <= rsi_sell_max):
            if cmd_manager.trading_side in ("BOTH", "SELL_ONLY"):
                reason = f"Downtrend (EMA{cmd_manager.fast_ema}={ema_fast:.2f} < EMA{cmd_manager.slow_ema}={ema_slow:.2f}), RSI={rsi:.1f} Bearish"
                return "SELL", reason, atr, "EMA_RSI", {}

        return "HOLD", f"Neutral. EMA_Fast={ema_fast:.2f}, EMA_Slow={ema_slow:.2f}, RSI={rsi:.1f}", atr, "NONE", {}


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
        """Check if trading is currently open for the symbol."""
        info = mt5.symbol_info(symbol)
        if not info or info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            return False

        # Crypto (BTC, ETH) trades 24/7 on Exness
        is_crypto = any(c in symbol.upper() for c in ["BTC", "ETH", "LTC", "XRP", "SOL"])
        if is_crypto:
            return True

        # Forex and Gold are closed on weekends (Saturday and Sunday until market open)
        now_utc = datetime.now(timezone.utc)
        weekday = now_utc.weekday()  # 5 = Saturday, 6 = Sunday
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

        spread_pips = (tick.ask - tick.bid) / (info.point * 10)
        limit = cmd_manager.max_spread_gold if "XAU" in symbol else cmd_manager.max_spread_forex
        if spread_pips > limit:
            logger.warning(f"Spread on {symbol} is {spread_pips:.1f} pips (Limit: {limit:.1f}). Skipping.")
            return False
        return True

    @classmethod
    def open_trade(cls, symbol: str, side: str, atr: float, reason: str, strategy_type: str = "EMA_RSI", struct_info: Optional[Dict[str, Any]] = None) -> bool:
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
                target_sl = (inval - buffer) if inval else (tick.ask - (cmd_manager.gold_sl_usd if is_gold else cmd_manager.forex_sl_pips * point * 10))
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
                target_sl = (inval + buffer) if inval else (tick.bid + (cmd_manager.gold_sl_usd if is_gold else cmd_manager.forex_sl_pips * point * 10))
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
        elif strategy_type == "H4_SNR":
            # Fallback Fixed SL & 1:2 R:R
            if is_gold:
                sl_distance = max(cmd_manager.gold_sl_usd, min_stop_dist)
            else:
                sl_distance = max(cmd_manager.forex_sl_pips * point * 10, min_stop_dist)
            tp_distance = sl_distance * cmd_manager.risk_reward_ratio

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
        else:
            # Regular EMA + RSI (ATR based)
            sl_distance = max(atr * cmd_manager.sl_atr_multiplier, min_stop_dist)
            tp_distance = max(atr * cmd_manager.tp_atr_multiplier, sl_distance * 2.0)
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
            "comment": "ExnessCmdBot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Check broker filling mode
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

        if result is None:
            logger.error(f"Order failed: {mt5.last_error()}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.warning(f"Direct order returned {result.retcode} ({result.comment}). Trying Market deal...")
            # Fallback for Market Execution accounts
            request["sl"] = 0.0
            request["tp"] = 0.0
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Market deal filled (#{result.deal}). Modifying SL/TP...")
                cls._modify_position_sl(result.order, sl, tp)
                return True
            else:
                logger.error(f"Order rejected: {result.comment if result else 'Unknown'}")
                return False

        logger.info(f"✅ [ORDER EXECUTED] Deal Ticket: #{result.deal} | Order Ticket: #{result.order} | Price: {result.price}")
        return True

    @classmethod
    def manage_trailing_stop(cls, symbol: str):
        if not cmd_manager.use_trailing_stop:
            return

        positions = cls.get_open_positions(symbol)
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not positions or not tick:
            return

        point = info.point
        digits = info.digits

        for pos in positions:
            if pos.type == mt5.ORDER_TYPE_BUY:
                profit_pips = (tick.bid - pos.price_open) / (point * 10)
                if profit_pips >= cmd_manager.trailing_start_pips:
                    new_sl = round(tick.bid - (cmd_manager.trailing_step_pips * point * 10), digits)
                    if new_sl > pos.sl and new_sl > pos.price_open:
                        logger.info(f"📈 [TRAILING STOP] Moving BUY #{pos.ticket} SL to {new_sl} (Locking Profit)")
                        cls._modify_position_sl(pos.ticket, new_sl, pos.tp)

            elif pos.type == mt5.ORDER_TYPE_SELL:
                profit_pips = (pos.price_open - tick.ask) / (point * 10)
                if profit_pips >= cmd_manager.trailing_start_pips:
                    new_sl = round(tick.ask + (cmd_manager.trailing_step_pips * point * 10), digits)
                    if (pos.sl == 0.0 or new_sl < pos.sl) and new_sl < pos.price_open:
                        logger.info(f"📉 [TRAILING STOP] Moving SELL #{pos.ticket} SL to {new_sl} (Locking Profit)")
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
            logger.info(f"SL/TP successfully updated on ticket #{ticket}")


# =============================================================================
# MAIN AUTOTRADER CONTROLLER
# =============================================================================
class ExnessAutoBot:
    """The central trading loop that executes instructions from bot_commands.json."""

    def __init__(self):
        self.symbol_manager = SymbolManager()
        self.active_symbols: Dict[str, str] = {}
        self.is_running = False

    def initialize(self) -> bool:
        logger.info("=" * 65)
        logger.info("   EXNESS MT5 DIRECT AUTO-TRADING BOT")
        logger.info("=" * 65)

        logger.info("Connecting to MetaTrader 5...")
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed! Error code: {mt5.last_error()}")
            logger.info("Please ensure Exness MetaTrader 5 desktop application is open and logged in.")
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
        logger.info(f"   Algo Trading  : {'ENABLED' if terminal.trade_allowed else 'DISABLED ⚠️ (Enable Algo Trading in MT5)'}")
        logger.info("-" * 65)

        # Discover symbols specified in bot_commands.json
        self.active_symbols = self.symbol_manager.discover_symbols(cmd_manager.active_symbols)
        if not self.active_symbols:
            logger.error("No trading symbols matched. Exiting.")
            return False

        return True

    def run(self):
        self.is_running = True
        logger.info("🚀 BOT IS RUNNING. Live listening to bot_commands.json...")
        logger.info(f"Active Pairs: {list(self.active_symbols.keys())} | Lot: {cmd_manager.lot_size}")
        logger.info("=" * 65)

        try:
            while self.is_running:
                # 1. Hot-reload bot_commands.json if changed
                if cmd_manager.load():
                    # Re-sync symbol discovery if active_symbols changed
                    self.active_symbols = self.symbol_manager.discover_symbols(cmd_manager.active_symbols)

                account = mt5.account_info()
                if not account:
                    time.sleep(5)
                    continue

                total_open = len(OrderExecutor.get_open_positions())

                # Loop through target instruments
                for base_name, actual_symbol in self.active_symbols.items():
                    # Manage Trailing Stops on open positions
                    OrderExecutor.manage_trailing_stop(actual_symbol)

                    # Check if market is open (Forex/Gold closed on weekends, Crypto open 24/7)
                    if not OrderExecutor.is_market_open(actual_symbol):
                        continue

                    # Check Pause flag from bot_commands.json
                    if cmd_manager.pause_trading:
                        continue

                    # Check max open positions
                    symbol_positions = OrderExecutor.get_open_positions(actual_symbol)
                    if len(symbol_positions) >= cmd_manager.max_open_per_pair:
                        continue

                    if total_open >= cmd_manager.max_total_open:
                        continue

                    # Evaluate Strategy Signals (Returns signal, reason, atr, strategy_type, struct_info)
                    signal, reason, atr, strat_type, struct_info = StrategyEngine.evaluate(actual_symbol)

                    tick = mt5.symbol_info_tick(actual_symbol)
                    bid_price = tick.bid if tick else 0.0

                    now_str = datetime.now().strftime("%H:%M:%S")
                    if signal in ("BUY", "SELL"):
                        logger.info(f"[{now_str}] 🎯 SIGNAL DETECTED: {base_name} ({actual_symbol}) -> {signal} | Strategy: {strat_type} | Rate: {bid_price:.2f}")
                        logger.info(f"         Reason: {reason}")
                        OrderExecutor.open_trade(actual_symbol, signal, atr, reason, strategy_type=strat_type, struct_info=struct_info)

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
