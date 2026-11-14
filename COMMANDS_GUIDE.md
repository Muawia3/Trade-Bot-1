# 📖 BOT COMMANDS & TRAINING GUIDE (Exness MT5)

Yeh guide aapko batati hai ke aap [`bot_commands.json`](file:///e:/Muawia/Trading%20Bot/bot_commands.json) file me bot ko kaise nayi commands de sakte hain aur uski trading strategy ko train/adjust kar sakte hain.

Bot har **10 second** baad is file ko check karta hai. Jaise hi aap file me koi tabdeeli karke **Save (Ctrl + S)** karenge, bot foran naye rules apply kar dega (bot ko restart karne ki bhi zaroorat nahi hai!).

---

## 🛠️ Commands Ki Tafseel (Har Command Kya Karti Hai)

### 1. General Commands (`general`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"pause_trading"` | `false` | Agar `true` kardein to bot naye trades lena band kar dega. Existing trades open rahengi. |
| `"trading_side"` | `"BOTH"` | `"BOTH"` (BUY aur SELL dono karega), `"BUY_ONLY"` (sirf Buy trades lega), `"SELL_ONLY"` (sirf Sell trades lega). |
| `"active_symbols"` | `["XAUUSD", "EURUSD"]` | Jin pairs par trade karni ho. Maslan: `["XAUUSD"]` (sirf Gold) ya `["XAUUSD", "EURUSD", "GBPUSD"]`. |
| `"check_interval_seconds"` | `10` | Har kitne second baad market ko scan kare. |

---

### 2. Money & Risk Management (`money_and_risk`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"use_fixed_lot"` | `false` | **Trade Calculation Ke Mutabiq Risk Management:** Agar `false` ho to bot har trade par Stop Loss ki doori aur account risk % ke mutabiq exact lot calculate karega. Agar `true` ho to hamesha fix lot size lagayega. |
| `"lot_size"` | `0.01` | Fixed Lot Size (jab `"use_fixed_lot": true` ho). |
| `"risk_percent_per_trade"` | `1.0` | **Mathematical Risk Control:** Har trade par account balance/equity ka kitne percent risk lena hai (e.g. 1.0% ya 2.0%). Chahe market structure ka SL bara ho ya chota, trade calculation se nuqsaan hamesha 1% hi rehta hai! |
| `"max_lot_size_limit"` | `0.50` | Bot kitni bari lot tak ja sakta hai (safety cap). |
| `"min_lot_size_limit"` | `0.01` | Minimum allowed lot size. |
| `"max_open_positions_per_pair"` | `1` | Ek waqt me ek pair (e.g. Gold) par kitni trades open reh sakti hain. |
| `"max_total_open_positions"` | `2` | Poore account me ek sath maximum kitni trades open ho sakti hain. |
| `"max_daily_loss_usd"` | `50.0` | **Circuit Breaker:** Agar kisi din \$50 loss ho jaye to bot us din ke liye khud trading band kar dega. |
| `"take_profit_daily_target_usd"` | `100.0` | Agar din ka target (\$100) achieve ho jaye to mazeed risk nahi lega. |

---

### 3. Strategy & Technical Indicators (`strategy_settings`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"timeframe"` | `"M5"` | Entry chart ka timeframe: `"M1"`, `"M5"` (5-minute), `"M15"`. |
| `"fast_ema_period"` | `20` | Fast Moving Average (Short-term momentum). |
| `"slow_ema_period"` | `50` | Slow Moving Average (Medium-term trend). |
| `"trend_ema_period"` | `200` | 200 EMA — Market ka major trend baseline. |
| `"rsi_period"` | `14` | RSI indicator ki period. |
| `"rsi_buy_min"` / `"rsi_buy_max"` | `45.0` / `68.0` | BUY trade tab lagegi jab RSI is range me ho. |
| `"rsi_sell_min"` / `"rsi_sell_max"` | `32.0` / `55.0` | SELL trade tab lagegi jab RSI is range me ho. |
| `"require_trend_ema_filter"` | `true` | Agar `true` ho to sirf major trend ki simat me trade lega. |

---

### 3.1 Multi-Timeframe Strategy: H4 S&R + M15/M5 Engulfing (Dynamic Market Structure 1:2 R:R)

Yeh aik professional **Top-Down Price Action Strategy** hai jahan **Stop Loss aur Take Profit market structure ke hisab se dynamically calculate hote hain** (koi hardcoded $4 ya $8 zaruri nahi):

```
[H4 Chart: Major Support / Resistance Zone Identify Karna]
                           │
                           ▼ (Jab market H4 Key Level par pohnchti hai)
[M15 / M5 Timeframe Par Switch Hona]
                           │
                           ▼ (Candlestick Confirmation Ka Intezar)
      ┌────────────────────┴────────────────────┐
      ▼                                         ▼
[Support Par Bullish Engulfing Candle]    [Resistance Par Bearish Engulfing Candle]
      │                                         │
      ▼                                         ▼
   BUY Trade Trigger!                        SELL Trade Trigger!
   - Stop Loss: Engulfing Low & Support      - Stop Loss: Engulfing High & Resistance
     ke theek neeche (Market Structure SL)     ke theek upar (Market Structure SL)
   - Take Profit: Exact 2 × SL Distance      - Take Profit: Exact 2 × SL Distance
     (1:2 Dynamic Risk to Reward)              (1:2 Dynamic Risk to Reward)
   - Lot Size: Dynamic Risk Calculation      - Lot Size: Dynamic Risk Calculation
     (Chahe SL $2 ho ya $5, risk sirf 1%)      (Chahe SL $2 ho ya $5, risk sirf 1%)
```

#### 💡 Dynamic Stop Loss & Risk Reward Kaise Kaam Karta Hai?
1. **Market Structure Invalidation:**
   - **BUY Trade me:** Stop Loss engulfing candle ke Low aur Support level ke theek neeche (safety buffer ke sath) lagaya jata hai. Agar market is se neeche gir jaye to structure break ho jati hai.
   - **SELL Trade me:** Stop Loss engulfing candle ke High aur Resistance level ke theek upar lagaya jata hai.
2. **Exact 1:2 Risk to Reward Ratio:**
   - Bot market structure ke hisab se Stop Loss ki doori (points/dollars) naapta hai:
     - Maslan agar Gold par Engulfing candle ka SL **$2.50** banta hai, to Take Profit **$5.00** lagaya jayega.
     - Agar kisi trade par candle bari hone se SL **$4.20** banta hai, to Take Profit **$8.40** lagaya jayega!
   - Har trade par **Take Profit = 2 × Stop Loss** automatically calculate hota hai.
3. **Trade Calculation & Money Management (Dynamic Lot Sizing):**
   - Agar `"use_fixed_lot": false` ho, to bot lot size khud calculate karta hai:
     $$\text{Lot Size} = \frac{\text{Account Equity} \times 1\%}{\text{Market SL Distance} \times \text{Tick Value}}$$
   - Iska faida: Har trade par aapka loss sirf 1% (\$10) hi hoga chahe SL bara ho ya chota, aur TP hit hone par 2% (\$20) profit milega!

#### Commands Table for H4 S&R Strategy:
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"enabled"` | `true` | H4 Support/Resistance + Engulfing strategy ko chalu ya band karna. |
| `"entry_timeframe"` | `"M5"` | Confirmation ke liye chota timeframe (`"M5"` ya `"M15"`). |
| `"h4_lookback_candles"` | `40` | H4 par pichli kitni candles ka Support aur Resistance nikalna hai (40 candles = pichle 7 din ke major levels). |
| `"support_resistance_tolerance_pct"` | `0.25` | Level ke aas paas kitna buffer zone maana jaye (0.25% zone). |
| `"require_bullish_engulfing_at_support"` | `true` | Support par BUY sirf tab karega jab M5/M15 par **Green Bullish Engulfing** candle pichli Red candle ko poori tarah engulf (cover) kare. |
| `"require_bearish_engulfing_at_resistance"` | `true` | Resistance par SELL sirf tab karega jab M5/M15 par **Red Bearish Engulfing** candle pichli Green candle ko cover kare. |
| `"sl_calculation_mode"` | `"DYNAMIC_MARKET_STRUCTURE"` | `"DYNAMIC_MARKET_STRUCTURE"` (Candle low/high aur Support/Resistance ke hisab se) ya `"FIXED_POINTS"`. |
| `"risk_reward_ratio"` | `2.0` | **1:2 Ratio**: Har 1 dollar ke market risk par 2 dollar ka profit target (2.0 = 1:2, 3.0 = 1:3). |
| `"structure_sl_buffer_pips"` | `2.0` | Forex par candle extreme ke baad safety buffer pips. |
| `"structure_sl_buffer_gold_usd"` | `0.50` | Gold par candle low/high ke baad safety buffer (\$0.50). |
| `"gold_min_sl_usd"` | `1.5` | Gold par minimum SL limit (taake broker rejection na ho). |
| `"gold_max_sl_usd"` | `8.0` | Gold par maximum SL limit (taake kisi ajeeb lambi wick par bara SL na lag jaye). |
| `"forex_min_sl_pips"` | `10.0` | EURUSD minimum SL limit (10 pips). |
| `"forex_max_sl_pips"` | `45.0` | EURUSD maximum SL limit (45 pips). |

---

### 4. Stop Loss & Take Profit (`stop_loss_and_take_profit`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"stop_loss_atr_multiplier"` | `1.5` | Stop Loss kitna bara ho (1.5 × ATR volatility). |
| `"take_profit_atr_multiplier"` | `3.0` | Target Profit kitna bara ho (3.0 × ATR = 1:2 Risk/Reward). |
| `"use_trailing_stop"` | `true` | Profit ko automatically lock karne ke liye trailing stop. |
| `"trailing_activation_pips"` | `15.0` | Jab trade 15 pips profit me chali jaye tab trailing stop shuru hoga. |
| `"trailing_step_pips"` | `5.0` | Har 5 pips profit barhne par Stop Loss ko aage khinchta rahega. |

---

### 5. Advanced Filters (`advanced_filters`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"max_allowed_spread_pips_gold"` | `6.0` | Agar Gold ka spread 6 pips se zyada ho (e.g. news time par) to trade nahi lega. |
| `"max_allowed_spread_pips_forex"` | `3.0` | EURUSD spread limit. |
| `"avoid_weekend_holding"` | `true` | Weekend se pehle Friday close par trades safe rakhna. |
| `"avoid_high_impact_news"` | `true` | Bari US news (CPI, NFP, Fed) ke waqt trades ko rokay ga. |

---

## 🎯 Bot Ko Train / Preset Banane Ke Examples:

### Example A: "Sirf Gold Par Fast Scalping (M1)"
```json
{
  "general": {
    "active_symbols": ["XAUUSD"],
    "check_interval_seconds": 5
  },
  "strategy_settings": {
    "timeframe": "M1"
  },
  "stop_loss_and_take_profit": {
    "stop_loss_atr_multiplier": 1.0,
    "take_profit_atr_multiplier": 2.0,
    "trailing_activation_pips": 10.0
  }
}
```

### Example B: "H4 Support/Resistance + M5 Engulfing (Market Structure SL + 1:2 R:R + 1% Risk)"
Market ke actual levels ke mutabiq dynamic SL/TP aur automatic position sizing:
```json
{
  "money_and_risk": {
    "use_fixed_lot": false,
    "risk_percent_per_trade": 1.0
  },
  "h4_snr_engulfing_strategy": {
    "enabled": true,
    "entry_timeframe": "M5",
    "sl_calculation_mode": "DYNAMIC_MARKET_STRUCTURE",
    "risk_reward_ratio": 2.0,
    "structure_sl_buffer_gold_usd": 0.50,
    "gold_min_sl_usd": 1.5,
    "gold_max_sl_usd": 8.0
  }
}
```
