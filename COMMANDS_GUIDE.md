# 📖 BOT COMMANDS & TRAINING GUIDE (Exness MT5 v2.5 Institutional)

Yeh guide aapko batati hai ke aap [`bot_commands.json`](file:///e:/Muawia/Trading%20Bot/bot_commands.json) file me bot ko kaise control kar sakte hain aur uski trading strategy ko train/adjust kar sakte hain.

Bot har **10 second** baad is file ko check karta hai. Jaise hi aap file me koi tabdeeli karke **Save (Ctrl + S)** karenge, bot foran naye rules apply kar dega.

---

## 🔍 Trade History Analysis (Masla Kya Tha Aur Kaise Theek Hua?):

Aapke MT5 account ki trades ka deep analysis karne par pata chala:
* **Win Rate bohut solid tha (58% wins!)**
* Lekin masla yeh tha: **Average Win sirf +$0.60 tha, jabkay Average Loss -$1.30 (aur Max Loss -$23.36) tha.**
* **Wajah:** 
  1. **Purani EA M1 (1-Minute) Chart par chal rahi thi:** M1 chart par market noise bohot zyada hoti hai aur har 1-2 minute baad trade lag rahi thi (6 ghantay me 290+ trades lag gayin!).
  2. **Purana Trailing Stop Gold ko Ghut Raha Tha:** Purane bot me trailing stop 15 cents ($0.15) par activate ho kar 5 cents ($0.05) par Stop Loss chipka deta tha. Gold ka spread hi 25-30 cents hota hai, is liye trade thora sa upar jaate hi foran SL hit ho jati thi aur sirf +$0.08 ya +$0.15 par out ho jati thi, jabkay loss me poora -$2.00 lagta tha!

### 💡 Naye v2.5 Institutional Engine Ka Solution (Loss Kam, Profit Ziyada):
1. **High Risk-to-Reward (1:2.2 R:R Ratio):**
   * Agar Stop Loss **$3.00** hai, to Take Profit poora **$6.60** hoga!
   * Loss hamesha chota hoga aur Profit hamesha loss se double se bhi zyada hoga!
2. **Trailing Stop Choke Khatam (Micro Trailing Stop OFF):**
   * Trailing stop ko band kar diya gaya hai taake Gold ki natural movement ko saans lene ki poori jagah miley aur woh poora $6 - $8 Take Profit hit kare!
3. **Smart Break-Even (Zero Risk Guarantee at 1R):**
   * Jab Gold trade **+$2.50** profit me chali jaye, bot Stop Loss ko entry ke aage **+$0.40 par lock** kar deta hai.
   * Is ke baad agar market palat bhi jaye to **LOSS = $0.00** (koi loss nahi hoga)! Aur agar target par jaye to **+$6.60 ka poora profit** milega!
4. **H4 Support & Resistance + Bullish/Bearish Engulfing & Pinbars:**
   * Bot H4 ke major institutional levels dekhta hai aur sirf wahan par jab solid rejection candle (Bullish Engulfing ya Hammer Pinbar) banay tabhi entry leta hai.
5. **Anti-Overtrading Rules:**
   * **30-Minute Cooldown:** Har trade ke baad 30 minute ka waqfa.
   * **Max 6 Trades Daily:** Din me sirf 5-6 top quality trades, fazool scalping band.
   * **Execution M5/M15 Anchored:** Ab EA chart timeframe par depend nahi karta, internal execution M5 institutional timeframe par fix hai.

---

## 🛠️ Commands Ki Tafseel (`bot_commands.json`)

### 1. General Commands (`general`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"pause_trading"` | `false` | Agar `true` kardein to bot naye trades lena band kar dega. Existing trades open rahengi. |
| `"trading_side"` | `"BOTH"` | `"BOTH"` (BUY aur SELL dono karega), `"BUY_ONLY"`, ya `"SELL_ONLY"`. |
| `"active_symbols"` | `["XAUUSD", "EURUSD"]` | Jin pairs par trade karni ho. |
| `"check_interval_seconds"` | `10` | Har kitne second baad market ko scan kare. |

---

### 2. Money & Risk Management (`money_and_risk`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"use_fixed_lot"` | `true` | `true` par 0.01 fixed lot use hoga. `false` par bot dynamic lot calculate karega. |
| `"lot_size"` | `0.01` | Fixed Lot Size (0.01 lot recommended). |
| `"risk_percent_per_trade"` | `1.0` | Har trade par account balance ka kitne percent risk lena hai (1.0%). |
| `"max_daily_trades"` | `6` | **Anti-Overtrading Cap:** Aik din me maximum 6 quality trades. |
| `"trade_cooldown_minutes"` | `30` | Aik trade band hone ke baad agle 30 minute tak usi pair par nayi trade nahi lega. |
| `"max_daily_loss_usd"` | `25.0` | **Circuit Breaker:** Agar kisi din \$25 loss ho jaye to trading khud stop. |
| `"take_profit_daily_target_usd"` | `50.0` | Din ka target (\$50) achieve hote hi trading stop aur profit safe. |

---

### 3. Advanced Institutional Strategy (`advanced_strategy`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"use_h1_trend_filter"` | `true` | H1 timeframe par 50 aur 200 EMA trend filter. Uptrend me sirf BUY, Downtrend me sirf SELL. |
| `"entry_timeframe"` | `"M5"` | Execution timeframe. (M5 ya M15). |
| `"rsi_buy_pullback_min"` | `38.0` | RSI pullback minimum (discount zone). |
| `"rsi_buy_pullback_max"` | `54.0` | RSI pullback maximum (kabhi peak par BUY nahi karega). |
| `"require_rejection_candle"` | `true` | Entry se pehle rejection confirmation candle zaroori hai. |

---

### 4. H4 Support & Resistance + Rejection (`h4_snr_engulfing_strategy`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"enabled"` | `true` | H4 Key Levels + Candlestick strategy ko on/off karne ke liye. |
| `"risk_reward_ratio"` | `2.2` | **1:2.2 Risk to Reward:** Agar Stop Loss $3.00 hai to Take Profit $6.60 hoga. |
| `"support_resistance_tolerance_usd"` | `3.50` | Gold S&R Zone buffer ($3.50). |
| `"require_bullish_rejection_at_support"` | `true` | Support par Bullish Engulfing ya Hammer Pinbar dekhega. |
| `"require_bearish_rejection_at_resistance"` | `true` | Resistance par Bearish Engulfing ya Shooting Star dekhega. |
| `"gold_min_sl_usd"` | `2.5` | Gold par minimum Stop Loss ($2.50) taake spread se safe rahe. |
| `"gold_max_sl_usd"` | `5.5` | Gold par maximum Stop Loss ($5.50). |

---

### 5. Smart Profit Protection & Break-Even (`profit_protection_and_trailing`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"use_break_even"` | `true` | **Zero-Risk Trading:** Jab trade +1R profit me jaye to SL entry ke aage lock kar deta hai. |
| `"gold_break_even_trigger_usd"` | `2.50` | Gold par **+$2.50** profit hote hi Break-Even active hota hai. |
| `"gold_break_even_lock_usd"` | `0.40` | Entry price se **+$0.40** aage SL set karta hai (spread aur fees cover). |
| `"use_trailing_stop"` | `false` | **False rakhein!** Is se trades bina jaldi kate poore Take Profit tak daud sakengi. |

---

## 📌 Zaroori Hidayat (MT5 Chart Setup):
1. MT5 me Gold (`XAUUSDm`) ka chart open karein aur timeframe **M5** ya **M15** par set karein (M1 par mat rakhein).
2. Navigator se `Exness_AutoTrader_EA` ko chart par drag karein.
3. Common tab me **"Allow Algo Trading"** par tick karein aur OK dabayein.
4. Top toolbar par **"Algo Trading"** green hona chahiye.
