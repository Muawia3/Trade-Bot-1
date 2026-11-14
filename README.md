# Exness MT5 Auto-Trading Bot

Professional automated algorithmic trading bot designed specifically for **Exness MetaTrader 5** (Forex & Gold / XAUUSD).

---

## 📁 File Structure

| File | Purpose |
|:---|:---|
| **[exness_bot.py](file:///e:/Muawia/Trading%20Bot/exness_bot.py)** | Direct Python MT5 Automated Trader (Connects directly to your Exness MT5 terminal). |
| **[bot_commands.json](file:///e:/Muawia/Trading%20Bot/bot_commands.json)** | Live configuration file for bot rules, risk, timeframes, and strategies (Hot-reloads instantly upon save). |
| **[COMMANDS_GUIDE.md](file:///e:/Muawia/Trading%20Bot/COMMANDS_GUIDE.md)** | Complete user manual and Urdu guide explaining all commands and trading rules. |
| **[START_EXNESS_BOT.bat](file:///e:/Muawia/Trading%20Bot/START_EXNESS_BOT.bat)** | 1-Click desktop launcher to start the Python Bot. |
| **[Exness_AutoTrader_EA.mq5](file:///e:/Muawia/Trading%20Bot/Exness_AutoTrader_EA.mq5)** | Native MetaTrader 5 Expert Advisor source code (H4 S&R + Engulfing + 1:2 R:R). |
| **[Exness_AutoTrader_EA.ex5](file:///e:/Muawia/Trading%20Bot/Exness_AutoTrader_EA.ex5)** | Compiled MT5 Expert Advisor (Ready to drag & drop onto any MT5 chart). |
| **`exness_bot.log`** | Real-time execution logs of the running bot. |

---

## 🚀 How to Run

1. Open your **Exness MetaTrader 5** desktop terminal and make sure **Algo Trading** is enabled (Green icon in MT5 toolbar).
2. Double click **`START_EXNESS_BOT.bat`** (or run `python exness_bot.py`).
3. To customize trades, lot size, risk %, or strategies, open **`bot_commands.json`**, edit the values, and save. The bot updates immediately without restarting.
