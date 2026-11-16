# 📖 BOT COMMANDS & TRAINING GUIDE (Exness MT5 v2.0)

Yeh guide aapko batati hai ke aap [`bot_commands.json`](file:///e:/Muawia/Trading%20Bot/bot_commands.json) file me bot ko kaise control kar sakte hain aur uski trading strategy ko train/adjust kar sakte hain.

Bot har **10 second** baad is file ko check karta hai. Jaise hi aap file me koi tabdeeli karke **Save (Ctrl + S)** karenge, bot foran naye rules apply kar dega.

---

## 🔍 Trade History Analysis (Masla Kya Tha Aur Kaise Theek Hua?):

Humne aapke MT5 account ki **139 closed trades** ki history ka deep analysis kiya. Result:
* **Win Rate bohut acha tha (57% wins!)**
* Lekin masla yeh tha: **Average Win sirf +$0.69 tha, jabkay Average Loss -$1.45 (aur Max Loss -$23.36) tha.**
* **Wajah:** 
  1. **Purana Trailing Stop Gold par 15 cents ($0.15) par activate ho jata tha aur 5 cents ($0.05) par Stop Loss le aata tha.** Gold ka standard spread hi 20-30 cents hota hai, is liye jaise hi trade zara sa profit me aati thi, agle hi second trailing stop hit ho jata tha aur trade out ho jati thi!
  2. **Over-Trading:** Cooldown aur H1 trend filter na hone ki wajah se bot ne subah 5 ghantay me 139 trades le li theen!

### 💡 Naye v2.0 Engine Ka Solution:
1. **Smart Break-Even (Risk-Free Trade):** Jab Gold **+$2.50** profit me jaye to Stop Loss ko entry ke upar **+$0.50 profit par lock** kar deta hai. Ab trade kabhi loss me nahi ja sakti!
2. **Breathing Trailing Stop (Profits Run Karne Dein):** Trailing stop ab tabhi shuru hota hai jab trade **+$4.50** profit me ho, aur price se **$2.00 ka khula fasla** rakhta hai taake Gold ko $6-$10 ka poora Take Profit hit karne ki jagah miley!
3. **Anti-Overtrading Cooldown (25 Minutes):** Aik trade khatam hone ke baad bot foran doosri trade nahi lega balkay 25 minute cooldown karega.
4. **Institutional H1 Trend Pullback:** H1 (1-Hour) chart par jab tak 50 aur 200 EMA ka solid trend na ho, M5 par trade nahi lega.

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
| `"use_fixed_lot"` | `false` | `false` par bot har trade ka lot size equity aur risk % ke mutabiq khud calculate karta hai. |
| `"lot_size"` | `0.01` | Fixed Lot Size (jab `"use_fixed_lot": true` ho). |
| `"risk_percent_per_trade"` | `1.0` | Har trade par account balance/equity ka kitne percent risk lena hai (1.0%). Chahe SL bara ho ya chota, loss sirf 1% hi hoga! |
| `"max_daily_trades"` | `8` | **Anti-Overtrading Cap:** Aik din me maximum 8 quality trades (139 trades wala over-trading khatam). |
| `"trade_cooldown_minutes"` | `25` | Aik trade band hone ke baad agle 25 minute tak usi pair par nayi trade nahi lega (chop se bachne ke liye). |
| `"max_daily_loss_usd"` | `30.0` | **Circuit Breaker:** Agar kisi din \$30 loss ho jaye to trading khud stop. |
| `"take_profit_daily_target_usd"` | `60.0` | Din ka target (\$60) achieve hote hi bot safe ho jata hai. |

---

### 3. Institutional Trend & Pullback Strategy (`advanced_strategy`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"use_h1_trend_filter"` | `true` | **H1 Trend Anchor:** H1 chart par trend check karega. Uptrend me sirf BUY, Downtrend me sirf SELL. |
| `"entry_timeframe"` | `"M5"` | Entry chart ka timeframe (`"M5"`). |
| `"h1_trend_ema_fast"` / `"h1_trend_ema_slow"` | `50` / `200` | 50 EMA aur 200 EMA — Institutional Trend Direction. |
| `"require_pullback_to_ema"` | `true` | Market ki peak par buy nahi karega; jab price 20/50 EMA tak wapas pullback kare tabhi entry dekhega. |
| `"rsi_buy_pullback_min"` / `"max"` | `38.0` / `54.0` | Uptrend me jab RSI 38-54 ke discount zone me aaye tab BUY karega (overbought peak par nahi). |
| `"require_rejection_candle"` | `true` | EMA se reversal confirmation candle banne ke baad hi trade execute karega. |

---

### 4. Smart Profit Protection & Trailing Stop (`profit_protection_and_trailing`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"use_break_even"` | `true` | **100% Risk-Free Feature:** Jab trade 1R profit me jaye to Stop Loss ko entry ke aage le aayega. |
| `"gold_break_even_trigger_usd"` | `2.50` | Gold par jab **+$2.50** profit ho jaye to BE trigger hoga. |
| `"gold_break_even_lock_usd"` | `0.50` | Gold par **+$0.50** profit lock kar lega taake spread nikalne ke baad bhi profit rahe. |
| `"use_trailing_stop"` | `true` | Profits ko lock karne ke liye trailing stop. |
| `"gold_trailing_trigger_usd"` | `4.50` | Gold par jab **+$4.50** profit ho jaye tab trailing shuru hoga (pehle ki tarah 15 cents par suffocated nahi hoga!). |
| `"gold_trailing_distance_usd"` | `2.00` | Gold par trailing stop price se **$2.00** peeche rahega taake trade lambi chal sake aur $8-$10 ka poora TP hit kare! |
| `"forex_break_even_trigger_pips"` | `15.0` | EURUSD par 15 pips profit par BE. |
| `"forex_trailing_trigger_pips"` | `25.0` | EURUSD par 25 pips profit par trailing. |

---

### 5. Market Session & Spread Filters (`filters`)
| Command | Default | Kya Karti Hai? (Urdu) |
|:---|:---:|:---|
| `"active_sessions_only"` | `true` | Sirf London aur New York ke high-volume sessions me trade karega. |
| `"allowed_session_start_utc_hour"` | `7` | 07:00 UTC (London Open) se start. |
| `"allowed_session_end_utc_hour"` | `20` | 20:00 UTC (New York close) tak trade karega. Raat ka dead chop skip karega. |
| `"max_allowed_spread_gold_usd"` | `0.45` | Gold par agar spread \$0.45 se zyada ho to trade nahi lega. |
