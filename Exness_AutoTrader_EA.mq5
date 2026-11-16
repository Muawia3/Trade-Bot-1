//+------------------------------------------------------------------+
//|                                     Exness_AutoTrader_EA.mq5     |
//|               Professional Auto-Trading Bot for MT5 / Exness     |
//|                 Instruments: XAUUSD (Gold) & EURUSD (Forex)      |
//|         Version 2.5: Institutional Low-Loss, High-Reward System  |
//+------------------------------------------------------------------+
#property copyright "Exness AutoTrader Institutional"
#property link      "https://www.exness.com"
#property version   "2.50"
#property description "Institutional Quantitative Forex & Gold Robot for Exness MT5."
#property description "Features: H4 S&R Liquidity + Engulfing/Pinbar, H1 Trend Pullback, 1:2.2 R:R, Smart Break-Even."

#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Input Parameters ---
input group "=== 1. Risk & Money Management ==="
input bool            InpUseFixedLot          = true;        // Use Fixed Lot Size (true = Safe 0.01 lot)
input double          InpFixedLotSize         = 0.01;        // Fixed Lot Size
input double          InpRiskPercent          = 1.0;         // % Risk per Trade (if UseFixedLot = false)
input double          InpMinLotLimit          = 0.01;        // Minimum Allowed Lot
input double          InpMaxLotLimit          = 0.50;        // Maximum Allowed Lot
input int             InpMaxOpenPositions     = 1;           // Max Open Positions per Symbol
input int             InpCooldownMinutes      = 30;          // Cooldown between trades (Minutes)
input int             InpMaxDailyTrades       = 6;           // Max allowed trades per day (Quality over Quantity)
input ulong           InpMagicNumber          = 998877;      // Unique Magic Number

input group "=== 2. Strategy 1: H4 Support/Resistance + Rejection (1:2.2 R:R) ==="
input bool            InpUseH4_SNR            = true;        // Enable H4 S&R Strategy
input ENUM_TIMEFRAMES InpEntryTF              = PERIOD_M5;   // Confirmation Timeframe (M5 or M15)
input int             InpH4Lookback           = 40;          // H4 Lookback Bars
input double          InpGoldH4ZoneUSD        = 3.50;        // Gold S&R Zone buffer in USD ($3.50)
input double          InpForexH4ZonePips      = 12.0;        // Forex S&R Zone buffer in Pips (12 pips)
input bool            InpDynamicMarketSL      = true;        // Dynamic Market Structure SL (Candle Low/High)
input double          InpRiskRewardRatio      = 2.2;         // Risk to Reward Ratio (2.2 = 1:2.2)
input double          InpStructureBufferGold  = 0.60;        // Gold SL Buffer in USD ($0.60)
input double          InpStructureBufferPips  = 2.5;         // Forex SL Buffer in Pips (2.5 pips)
input double          InpGoldMinSL_USD        = 2.5;         // Gold Min SL in USD ($2.50)
input double          InpGoldMaxSL_USD        = 5.5;         // Gold Max SL in USD ($5.50)
input double          InpForexMinSL_Pips      = 12.0;        // Forex Min SL in Pips (12 pips)
input double          InpForexMaxSL_Pips      = 30.0;        // Forex Max SL in Pips (30 pips)
input double          InpGoldFallbackSL_USD   = 3.5;         // Fallback Gold Stop Loss in USD
input double          InpForexFallbackSL_Pips = 20.0;        // Fallback Forex Stop Loss in Pips

input group "=== 3. Strategy 2: Institutional H1 Trend + Value Pullback ==="
input bool            InpUseTrendPullback     = true;        // Enable H1 Trend + Value Pullback Strategy
input ENUM_TIMEFRAMES InpExecutionTF          = PERIOD_M5;   // Strategy 2 Execution Timeframe (M5)
input bool            InpUseH1TrendFilter     = true;        // Enforce H1 50/200 EMA Trend Direction
input int             InpFastEMAPeriod        = 20;          // Fast EMA Period (Dynamic Support/Resistance)
input int             InpSlowEMAPeriod        = 50;          // Slow EMA Period
input int             InpH1FastEMAPeriod      = 50;          // H1 Trend EMA Fast
input int             InpH1SlowEMAPeriod      = 200;         // H1 Trend EMA Slow
input int             InpRSIPeriod            = 14;          // RSI Period
input double          InpRSIBuyPullbackMin    = 38.0;        // Buy Pullback RSI Min (Oversold in Uptrend)
input double          InpRSIBuyPullbackMax    = 54.0;        // Buy Pullback RSI Max (Never buy at top!)
input double          InpRSISellPullbackMin   = 46.0;        // Sell Pullback RSI Min
input double          InpRSISellPullbackMax   = 62.0;        // Sell Pullback RSI Max
input int             InpATRPeriod            = 14;          // ATR Period (Volatility)

input group "=== 4. Smart Profit Protection (Break-Even - Risk Free Trading!) ==="
input bool            InpUseBreakEven         = true;        // Enable Break-Even (Risk-Free Trade at 1R)
input double          InpGoldBETrigger_USD    = 2.50;        // Gold Profit to activate BE ($2.50)
input double          InpGoldBELock_USD       = 0.40;        // Gold Profit to lock in ($0.40 covering spread/commissions)
input double          InpForexBETrigger_Pips  = 15.0;        // Forex Profit to activate BE (15 pips)
input double          InpForexBELock_Pips     = 2.0;         // Forex Profit to lock in (2 pips)

input group "=== 5. Trailing Stop (Disabled by default to let full TP hit!) ==="
input bool            InpUseTrailingStop      = false;       // Enable Trailing Stop (FALSE = let trades hit full TP!)
input double          InpGoldTrailTrigger_USD = 5.00;        // Gold Profit to activate Trailing ($5.00)
input double          InpGoldTrailDist_USD    = 2.50;        // Gold Trailing distance behind price ($2.50)
input double          InpForexTrailTrigger_Pips = 25.0;      // Forex Profit to activate Trailing (25 pips)
input double          InpForexTrailDist_Pips  = 12.0;        // Forex Trailing distance behind price (12 pips)

input group "=== 6. Market Session & Spread Filters ==="
input bool            InpActiveSessionsOnly   = true;        // Only Trade London & New York Sessions
input int             InpSessionStartUTC      = 7;           // Session Start UTC Hour (07:00 UTC London Open)
input int             InpSessionEndUTC        = 20;          // Session End UTC Hour (20:00 UTC NY Close)
input double          InpMaxSpreadGold_USD    = 0.45;        // Max Spread allowed for Gold ($0.45)
input double          InpMaxSpreadForex_Pips  = 2.0;         // Max Spread allowed for Forex (2.0 pips)

//--- Global Handles & Objects ---
CTrade         m_trade;
CSymbolInfo    m_symbol;
CPositionInfo  m_position;
CAccountInfo   m_account;

int            h_ema_fast     = INVALID_HANDLE;
int            h_ema_slow     = INVALID_HANDLE;
int            h_h1_ema_fast  = INVALID_HANDLE;
int            h_h1_ema_slow  = INVALID_HANDLE;
int            h_rsi          = INVALID_HANDLE;
int            h_atr          = INVALID_HANDLE;

datetime       g_last_trade_time = 0;
datetime       g_last_bar_time   = 0;
string         g_status_msg      = "Initializing...";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!m_symbol.Name(_Symbol))
   {
      Print("[ERROR] Failed to initialize symbol: ", _Symbol);
      return INIT_FAILED;
   }
   m_symbol.Refresh();
   m_symbol.RefreshRates();

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(30);
   m_trade.SetTypeFillingBySymbol(_Symbol);

   // Indicators are anchored to InpExecutionTF (M5) so chart TF cannot ruin execution!
   h_ema_fast    = iMA(_Symbol, InpExecutionTF, InpFastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_slow    = iMA(_Symbol, InpExecutionTF, InpSlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_h1_ema_fast = iMA(_Symbol, PERIOD_H1, InpH1FastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_h1_ema_slow = iMA(_Symbol, PERIOD_H1, InpH1SlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi         = iRSI(_Symbol, InpExecutionTF, InpRSIPeriod, PRICE_CLOSE);
   h_atr         = iATR(_Symbol, InpExecutionTF, InpATRPeriod);

   Print("=================================================================");
   Print("  EXNESS AUTO-TRADER EA v2.5 INSTITUTIONAL STARTED");
   Print("  Symbol         : ", _Symbol);
   Print("  Account        : ", m_account.Login(), " (", m_account.Currency(), ")");
   Print("  Balance        : $", DoubleToString(m_account.Balance(), 2));
   Print("  Execution TF   : M5 (Anchored to protect from M1 noise)");
   Print("  Risk/Reward    : 1:", DoubleToString(InpRiskRewardRatio, 1));
   Print("  Break-Even     : ENABLED (Gold: +$", InpGoldBETrigger_USD, " -> Lock +$", InpGoldBELock_USD, ")");
   Print("  Trailing Stop  : ", (InpUseTrailingStop ? "ENABLED" : "DISABLED (Trades run to full TP!)"));
   Print("  Trend Filter   : H1 50/200 EMA + Value Pullback");
   Print("=================================================================");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_ema_fast);
   IndicatorRelease(h_ema_slow);
   IndicatorRelease(h_h1_ema_fast);
   IndicatorRelease(h_h1_ema_slow);
   IndicatorRelease(h_rsi);
   IndicatorRelease(h_atr);
   Comment("");
   Print("Exness Auto-Trader EA stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Find H4 Support and Resistance Swing Fractall Levels             |
//+------------------------------------------------------------------+
void GetH4SupportResistance(double &supports[], double &resistances[])
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_H4, 0, InpH4Lookback, rates);
   if(copied < 10) return;

   int sup_count = 0;
   int res_count = 0;
   ArrayResize(supports, 20);
   ArrayResize(resistances, 20);

   for(int i = 2; i < copied - 2; i++)
   {
      if(rates[i].high > rates[i-1].high && rates[i].high > rates[i-2].high &&
         rates[i].high > rates[i+1].high && rates[i].high > rates[i+2].high)
      {
         if(res_count < 20) resistances[res_count++] = rates[i].high;
      }
      if(rates[i].low < rates[i-1].low && rates[i].low < rates[i-2].low &&
         rates[i].low < rates[i+1].low && rates[i].low < rates[i+2].low)
      {
         if(sup_count < 20) supports[sup_count++] = rates[i].low;
      }
   }
   ArrayResize(supports, sup_count);
   ArrayResize(resistances, res_count);
}

//+------------------------------------------------------------------+
//| Candlestick Pattern Detection (Bullish/Bearish Engulfing & Pinbar)|
//+------------------------------------------------------------------+
bool CheckBullishRejection(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return false;

   // 1. Bullish Engulfing
   bool prev_red   = (rates[1].close < rates[1].open);
   bool curr_green = (rates[0].close > rates[0].open);
   bool engulfs    = (rates[0].open <= rates[1].close * 1.0005) && (rates[0].close >= rates[1].open * 0.9995);
   if(prev_red && curr_green && engulfs) return true;

   // 2. Bullish Pinbar / Hammer Rejection
   double body       = MathAbs(rates[0].close - rates[0].open);
   double lower_wick = MathMin(rates[0].open, rates[0].close) - rates[0].low;
   double upper_wick = rates[0].high - MathMax(rates[0].open, rates[0].close);
   if(lower_wick >= (body * 1.8) && lower_wick > upper_wick && rates[0].close > rates[0].low + lower_wick * 0.4)
      return true;

   return false;
}

bool CheckBearishRejection(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return false;

   // 1. Bearish Engulfing
   bool prev_green = (rates[1].close > rates[1].open);
   bool curr_red   = (rates[0].close < rates[0].open);
   bool engulfs    = (rates[0].open >= rates[1].close * 0.9995) && (rates[0].close <= rates[1].open * 1.0005);
   if(prev_green && curr_red && engulfs) return true;

   // 2. Bearish Pinbar / Shooting Star Rejection
   double body       = MathAbs(rates[0].close - rates[0].open);
   double upper_wick = rates[0].high - MathMax(rates[0].open, rates[0].close);
   double lower_wick = MathMin(rates[0].open, rates[0].close) - rates[0].low;
   if(upper_wick >= (body * 1.8) && upper_wick > lower_wick && rates[0].close < rates[0].high - upper_wick * 0.4)
      return true;

   return false;
}

double GetPatternLow(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return 0.0;
   return MathMin(rates[0].low, rates[1].low);
}

double GetPatternHigh(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return 0.0;
   return MathMax(rates[0].high, rates[1].high);
}

//+------------------------------------------------------------------+
//| Calculate Closed Trades Today (Anti-Overtrading)                 |
//+------------------------------------------------------------------+
int CountTradesToday()
{
   datetime start_of_day = (datetime)(TimeCurrent() - (TimeCurrent() % 86400));
   HistorySelect(start_of_day, TimeCurrent());
   int total_deals = HistoryDealsTotal();
   int trades = 0;
   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
      {
         if(HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol)
            trades++;
      }
   }
   return trades;
}

//+------------------------------------------------------------------+
//| Check Trading Session & Spread                                   |
//+------------------------------------------------------------------+
bool IsSpreadAndSessionAllowed(bool is_gold, double bid, double ask)
{
   // Check Session
   if(InpActiveSessionsOnly)
   {
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      if(dt.hour < InpSessionStartUTC || dt.hour >= InpSessionEndUTC)
      {
         g_status_msg = "Outside active London/NY trading hours. Waiting for session open (07:00 UTC)...";
         return false;
      }
   }

   // Check Spread
   double spread = ask - bid;
   if(is_gold)
   {
      if(spread > InpMaxSpreadGold_USD)
      {
         g_status_msg = "Gold spread too high ($" + DoubleToString(spread, 2) + " > $" + DoubleToString(InpMaxSpreadGold_USD, 2) + "). Skipping.";
         return false;
      }
   }
   else
   {
      double spread_pips = spread / (_Point * 10.0);
      if(spread_pips > InpMaxSpreadForex_Pips)
      {
         g_status_msg = "Forex spread too high (" + DoubleToString(spread_pips, 1) + " pips). Skipping.";
         return false;
      }
   }

   return true;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double bid = tick.bid;
   double ask = tick.ask;
   if(bid <= 0.0 || ask <= 0.0) return;

   bool is_gold = (StringFind(_Symbol, "XAU") >= 0);

   // 1. ALWAYS MANAGE OPEN POSITIONS: Smart Break-Even (Zero Risk at 1R)
   ApplyProfitProtectionAndTrailing(bid, ask, is_gold);

   double cur_price = bid;
   int open_pos     = CountOpenPositions();
   double balance   = m_account.Balance();

   if(balance <= 0.0)
   {
      g_status_msg = "⚠️ ACCOUNT BALANCE IS $0.00! Please deposit funds to trade.";
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
      return;
   }

   // If already holding max positions, don't open more
   if(open_pos >= InpMaxOpenPositions)
   {
      g_status_msg = "Position ACTIVE. Protected by 1R Break-Even & Full 1:2.2 TP Target.";
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
      return;
   }

   // 2. CHECK COOLDOWN (Anti-Overtrading - Quality Over Quantity)
   if(TimeCurrent() - g_last_trade_time < InpCooldownMinutes * 60)
   {
      int remain_sec = (int)((InpCooldownMinutes * 60) - (TimeCurrent() - g_last_trade_time));
      g_status_msg = "Cooldown active (" + IntegerToString(remain_sec / 60) + "m " + IntegerToString(remain_sec % 60) + "s remaining). Waiting for high quality setup.";
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
      return;
   }

   // 3. CHECK DAILY TRADE CAP
   int today_trades = CountTradesToday();
   if(today_trades >= InpMaxDailyTrades)
   {
      g_status_msg = "Daily trade limit reached (" + IntegerToString(today_trades) + "/" + IntegerToString(InpMaxDailyTrades) + "). Target protected for today.";
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
      return;
   }

   // 4. CHECK SESSION & SPREAD
   if(!IsSpreadAndSessionAllowed(is_gold, bid, ask))
   {
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
      return;
   }

   datetime current_bar_time = iTime(_Symbol, InpExecutionTF, 0);
   int stop_level_points = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double min_stop_dist = MathMax(stop_level_points * _Point, (ask - bid) * 2.0);

   // -------------------------------------------------------------
   // STRATEGY 1: H4 SUPPORT/RESISTANCE + M15/M5 REJECTION (1:2.2 R:R)
   // -------------------------------------------------------------
   if(InpUseH4_SNR)
   {
      double supports[], resistances[];
      GetH4SupportResistance(supports, resistances);

      double zone_dist = is_gold ? InpGoldH4ZoneUSD : (InpForexH4ZonePips * _Point * 10.0);
      double near_support = 0.0;
      double near_resistance = 0.0;

      for(int i = 0; i < ArraySize(supports); i++)
      {
         if(MathAbs(cur_price - supports[i]) <= zone_dist)
         {
            near_support = supports[i];
            break;
         }
      }

      for(int i = 0; i < ArraySize(resistances); i++)
      {
         if(MathAbs(cur_price - resistances[i]) <= zone_dist)
         {
            near_resistance = resistances[i];
            break;
         }
      }

      // Support + Bullish Rejection (Engulfing or Hammer Pinbar) -> BUY
      if(near_support > 0.0 && CheckBullishRejection(InpEntryTF))
      {
         g_status_msg = "🎯 H4 Support + Bullish Rejection! Executing BUY (1:2.2 R:R)...";
         if(current_bar_time != g_last_bar_time)
         {
            g_last_bar_time = current_bar_time;
            double sl_dist = 0.0;
            if(InpDynamicMarketSL)
            {
               double pat_low = GetPatternLow(InpEntryTF);
               double inval = (pat_low > 0.0) ? MathMin(pat_low, near_support) : near_support;
               double buf = is_gold ? InpStructureBufferGold : (InpStructureBufferPips * _Point * 10.0);
               sl_dist = ask - (inval - buf);
               if(is_gold)
                  sl_dist = MathMax(InpGoldMinSL_USD, MathMin(sl_dist, InpGoldMaxSL_USD));
               else
                  sl_dist = MathMax(InpForexMinSL_Pips * _Point * 10.0, MathMin(sl_dist, InpForexMaxSL_Pips * _Point * 10.0));
            }
            else
            {
               sl_dist = is_gold ? InpGoldFallbackSL_USD : (InpForexFallbackSL_Pips * _Point * 10.0);
            }
            sl_dist = MathMax(sl_dist, min_stop_dist);
            double tp_dist = sl_dist * InpRiskRewardRatio;

            double sl = NormalizeDouble(ask - sl_dist, _Digits);
            double tp = NormalizeDouble(ask + tp_dist, _Digits);
            double lot = CalculateLot(sl_dist);

            if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "H4_SNR_BUY"))
            {
               g_last_trade_time = TimeCurrent();
               Print("✅ [H4 S&R BUY EXECUTED] Lot: ", lot, " | Price: ", ask, " | SL: ", sl, " | TP: ", tp, " | R:R: 1:", InpRiskRewardRatio);
               g_status_msg = "H4 S&R BUY Executed (SL: " + DoubleToString(sl_dist, 2) + ", TP: " + DoubleToString(tp_dist, 2) + ")!";
            }
         }
         UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
         return;
      }

      // Resistance + Bearish Rejection (Engulfing or Shooting Star) -> SELL
      if(near_resistance > 0.0 && CheckBearishRejection(InpEntryTF))
      {
         g_status_msg = "🎯 H4 Resistance + Bearish Rejection! Executing SELL (1:2.2 R:R)...";
         if(current_bar_time != g_last_bar_time)
         {
            g_last_bar_time = current_bar_time;
            double sl_dist = 0.0;
            if(InpDynamicMarketSL)
            {
               double pat_high = GetPatternHigh(InpEntryTF);
               double inval = (pat_high > 0.0) ? MathMax(pat_high, near_resistance) : near_resistance;
               double buf = is_gold ? InpStructureBufferGold : (InpStructureBufferPips * _Point * 10.0);
               sl_dist = (inval + buf) - bid;
               if(is_gold)
                  sl_dist = MathMax(InpGoldMinSL_USD, MathMin(sl_dist, InpGoldMaxSL_USD));
               else
                  sl_dist = MathMax(InpForexMinSL_Pips * _Point * 10.0, MathMin(sl_dist, InpForexMaxSL_Pips * _Point * 10.0));
            }
            else
            {
               sl_dist = is_gold ? InpGoldFallbackSL_USD : (InpForexFallbackSL_Pips * _Point * 10.0);
            }
            sl_dist = MathMax(sl_dist, min_stop_dist);
            double tp_dist = sl_dist * InpRiskRewardRatio;

            double sl = NormalizeDouble(bid + sl_dist, _Digits);
            double tp = NormalizeDouble(bid - tp_dist, _Digits);
            double lot = CalculateLot(sl_dist);

            if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "H4_SNR_SELL"))
            {
               g_last_trade_time = TimeCurrent();
               Print("✅ [H4 S&R SELL EXECUTED] Lot: ", lot, " | Price: ", bid, " | SL: ", sl, " | TP: ", tp, " | R:R: 1:", InpRiskRewardRatio);
               g_status_msg = "H4 S&R SELL Executed (SL: " + DoubleToString(sl_dist, 2) + ", TP: " + DoubleToString(tp_dist, 2) + ")!";
            }
         }
         UpdateChartDashboard(balance, cur_price, 0, 0, 0, 0, open_pos);
         return;
      }
   }

   // -----------------------------------------------------------------
   // STRATEGY 2: INSTITUTIONAL H1 TREND + VALUE PULLBACK (HIGH WIN-RATE)
   // -----------------------------------------------------------------
   if(InpUseTrendPullback)
   {
      double ema_fast[2], ema_slow[2], rsi[2], atr[1];
      double h1_fast[1], h1_slow[1];

      if(CopyBuffer(h_ema_fast, 0, 0, 2, ema_fast) < 2) return;
      if(CopyBuffer(h_ema_slow, 0, 0, 2, ema_slow) < 2) return;
      if(CopyBuffer(h_rsi, 0, 0, 2, rsi) < 2) return;
      if(CopyBuffer(h_atr, 0, 0, 1, atr) < 1) return;
      if(CopyBuffer(h_h1_ema_fast, 0, 0, 1, h1_fast) < 1) return;
      if(CopyBuffer(h_h1_ema_slow, 0, 0, 1, h1_slow) < 1) return;

      double cur_rsi      = rsi[0];
      double cur_fast     = ema_fast[0];
      double cur_slow     = ema_slow[0];
      double cur_atr      = atr[0];
      double cur_h1_fast  = h1_fast[0];
      double cur_h1_slow  = h1_slow[0];

      // H1 Institutional Trend Bias
      bool h1_bullish = (!InpUseH1TrendFilter) || (cur_price > cur_h1_fast && cur_h1_fast > cur_h1_slow);
      bool h1_bearish = (!InpUseH1TrendFilter) || (cur_price < cur_h1_fast && cur_h1_fast < cur_h1_slow);

      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      if(CopyRates(_Symbol, InpExecutionTF, 1, 2, rates) < 2) return;

      // BUY Pullback: H1 is Bullish + Price pulled back into 20/50 EMA + RSI in discount + Green rejection candle
      bool buy_pullback = h1_bullish &&
                          (cur_fast > cur_slow) &&
                          (rates[0].low <= cur_fast * 1.0015) &&
                          (cur_rsi >= InpRSIBuyPullbackMin && cur_rsi <= InpRSIBuyPullbackMax) &&
                          (rates[0].close > rates[0].open);

      // SELL Pullback: H1 is Bearish + Price rallied into 20/50 EMA + RSI in premium + Red rejection candle
      bool sell_pullback = h1_bearish &&
                           (cur_fast < cur_slow) &&
                           (rates[0].high >= cur_fast * 0.9985) &&
                           (cur_rsi >= InpRSISellPullbackMin && cur_rsi <= InpRSISellPullbackMax) &&
                           (rates[0].close < rates[0].open);

      if(buy_pullback && current_bar_time != g_last_bar_time)
      {
         g_last_bar_time = current_bar_time;
         double sl_dist = MathMax(cur_atr * 1.8, min_stop_dist);
         if(is_gold) sl_dist = MathMax(InpGoldMinSL_USD, MathMin(sl_dist, InpGoldMaxSL_USD));
         double tp_dist = sl_dist * InpRiskRewardRatio; // 1:2.2 R:R

         double sl = NormalizeDouble(ask - sl_dist, _Digits);
         double tp = NormalizeDouble(ask + tp_dist, _Digits);
         double lot = CalculateLot(sl_dist);

         if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "INST_TREND_BUY"))
         {
            g_last_trade_time = TimeCurrent();
            Print("✅ [INSTITUTIONAL BUY EXECUTED] Lot: ", lot, " | Price: ", ask, " | SL: ", sl, " | TP: ", tp, " | Target: +$", DoubleToString(tp_dist, 2));
            g_status_msg = "Institutional Trend BUY Executed (1:2.2 R:R)! Target: +$" + DoubleToString(tp_dist, 2);
         }
      }
      else if(sell_pullback && current_bar_time != g_last_bar_time)
      {
         g_last_bar_time = current_bar_time;
         double sl_dist = MathMax(cur_atr * 1.8, min_stop_dist);
         if(is_gold) sl_dist = MathMax(InpGoldMinSL_USD, MathMin(sl_dist, InpGoldMaxSL_USD));
         double tp_dist = sl_dist * InpRiskRewardRatio; // 1:2.2 R:R

         double sl = NormalizeDouble(bid + sl_dist, _Digits);
         double tp = NormalizeDouble(bid - tp_dist, _Digits);
         double lot = CalculateLot(sl_dist);

         if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "INST_TREND_SELL"))
         {
            g_last_trade_time = TimeCurrent();
            Print("✅ [INSTITUTIONAL SELL EXECUTED] Lot: ", lot, " | Price: ", bid, " | SL: ", sl, " | TP: ", tp, " | Target: +$", DoubleToString(tp_dist, 2));
            g_status_msg = "Institutional Trend SELL Executed (1:2.2 R:R)! Target: +$" + DoubleToString(tp_dist, 2);
         }
      }
      else
      {
         g_status_msg = "H1 Trend: " + (h1_bullish ? "BULLISH 🟢" : (h1_bearish ? "BEARISH 🔴" : "NEUTRAL/CHOP ⚪")) + " | Waiting for clean value pullback...";
      }

      UpdateChartDashboard(balance, cur_price, cur_rsi, cur_fast, cur_slow, cur_h1_fast, open_pos);
   }
}

//+------------------------------------------------------------------+
//| SMART PROFIT PROTECTION (BREAK-EVEN & BREATHING TRAILING)        |
//+------------------------------------------------------------------+
void ApplyProfitProtectionAndTrailing(double bid, double ask, bool is_gold)
{
   double point = _Point;

   double be_trigger    = is_gold ? InpGoldBETrigger_USD : (InpForexBETrigger_Pips * point * 10.0);
   double be_lock       = is_gold ? InpGoldBELock_USD    : (InpForexBELock_Pips * point * 10.0);
   double trail_trigger = is_gold ? InpGoldTrailTrigger_USD : (InpForexTrailTrigger_Pips * point * 10.0);
   double trail_dist    = is_gold ? InpGoldTrailDist_USD    : (InpForexTrailDist_Pips * point * 10.0);

   int stop_level_points = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double min_stop_dist  = MathMax(stop_level_points * point, (ask - bid) * 1.5);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() != _Symbol || m_position.Magic() != InpMagicNumber)
            continue;

         ulong ticket      = m_position.Ticket();
         double open_price = m_position.PriceOpen();
         double current_sl = m_position.StopLoss();
         double current_tp = m_position.TakeProfit();

         if(m_position.PositionType() == POSITION_TYPE_BUY)
         {
            double profit_dist = bid - open_price;

            // 1. SMART BREAK-EVEN: Lock in risk-free trade at 1R profit
            if(InpUseBreakEven && profit_dist >= be_trigger)
            {
               double be_sl = NormalizeDouble(open_price + be_lock, _Digits);
               if(current_sl < be_sl && (bid - be_sl) > min_stop_dist)
               {
                  if(m_trade.PositionModify(ticket, be_sl, current_tp))
                     Print("🛡️ [BREAK-EVEN] BUY #", ticket, " SL secured to: ", be_sl, " (Trade is now 100% Risk-Free!)");
               }
            }

            // 2. BREATHING TRAILING STOP (Only if enabled, wide room)
            if(InpUseTrailingStop && profit_dist >= trail_trigger)
            {
               double new_sl = NormalizeDouble(bid - trail_dist, _Digits);
               if(new_sl > current_sl && new_sl > open_price && (bid - new_sl) > min_stop_dist)
               {
                  if(m_trade.PositionModify(ticket, new_sl, current_tp))
                     Print("📈 [TRAILING STOP] BUY #", ticket, " SL adjusted to: ", new_sl, " (Locked: +$", DoubleToString(new_sl - open_price, 2), ")");
               }
            }
         }
         else if(m_position.PositionType() == POSITION_TYPE_SELL)
         {
            double profit_dist = open_price - ask;

            // 1. SMART BREAK-EVEN: Lock in risk-free trade at 1R profit
            if(InpUseBreakEven && profit_dist >= be_trigger)
            {
               double be_sl = NormalizeDouble(open_price - be_lock, _Digits);
               if((current_sl == 0.0 || current_sl > be_sl) && (be_sl - ask) > min_stop_dist)
               {
                  if(m_trade.PositionModify(ticket, be_sl, current_tp))
                     Print("🛡️ [BREAK-EVEN] SELL #", ticket, " SL secured to: ", be_sl, " (Trade is now 100% Risk-Free!)");
               }
            }

            // 2. BREATHING TRAILING STOP
            if(InpUseTrailingStop && profit_dist >= trail_trigger)
            {
               double new_sl = NormalizeDouble(ask + trail_dist, _Digits);
               if((current_sl == 0.0 || new_sl < current_sl) && new_sl < open_price && (new_sl - ask) > min_stop_dist)
               {
                  if(m_trade.PositionModify(ticket, new_sl, current_tp))
                     Print("📉 [TRAILING STOP] SELL #", ticket, " SL adjusted to: ", new_sl, " (Locked: +$", DoubleToString(open_price - new_sl, 2), ")");
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Lot Size based on Risk and Broker Contract Specs       |
//+------------------------------------------------------------------+
double CalculateLot(double stop_loss_distance)
{
   if(InpUseFixedLot)
   {
      double lot = InpFixedLotSize;
      double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      if(min_lot <= 0) min_lot = 0.01;
      if(max_lot <= 0) max_lot = 100.0;
      return NormalizeDouble(MathMax(min_lot, MathMin(lot, max_lot)), 2);
   }

   double equity = m_account.Equity();
   double risk_amount = equity * (InpRiskPercent / 100.0);
   double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tick_val > 0 && tick_size > 0 && stop_loss_distance > 0)
   {
      double loss_per_lot = (stop_loss_distance / tick_size) * tick_val;
      if(loss_per_lot > 0)
      {
         double raw_lot = risk_amount / loss_per_lot;
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         if(step <= 0) step = 0.01;
         double lot = MathFloor(raw_lot / step) * step;
         double min_lot = MathMax(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), InpMinLotLimit);
         double max_lot = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), InpMaxLotLimit);
         return NormalizeDouble(MathMax(min_lot, MathMin(lot, max_lot)), 2);
      }
   }

   return InpMinLotLimit;
}

//+------------------------------------------------------------------+
//| Count Open Positions for this EA on the current Symbol           |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Update Chart On-Screen Dashboard                                 |
//+------------------------------------------------------------------+
void UpdateChartDashboard(double balance, double price, double rsi, double fast, double slow, double h1_fast, int open_pos)
{
   string text = "";
   text += "=====================================================\n";
   text += "     EXNESS AUTO-TRADER v2.5 INSTITUTIONAL\n";
   text += "=====================================================\n";
   text += " Account Login : " + IntegerToString(m_account.Login()) + " (" + m_account.Currency() + ")\n";
   text += " Balance       : $" + DoubleToString(balance, 2) + "\n";
   text += " Equity        : $" + DoubleToString(m_account.Equity(), 2) + "\n";
   text += " Open Trades   : " + IntegerToString(open_pos) + " / " + IntegerToString(InpMaxOpenPositions) + "\n";
   text += " Trades Today  : " + IntegerToString(CountTradesToday()) + " / " + IntegerToString(InpMaxDailyTrades) + "\n";
   text += " Status        : " + g_status_msg + "\n";
   text += "-----------------------------------------------------\n";
   text += " Risk : Reward : 1 : " + DoubleToString(InpRiskRewardRatio, 1) + " (High Profit Strategy)\n";
   text += " Break-Even    : At +$" + DoubleToString(InpGoldBETrigger_USD, 2) + " -> Locks +$" + DoubleToString(InpGoldBELock_USD, 2) + " (Zero Risk)\n";
   text += " Trailing Stop : " + (InpUseTrailingStop ? ("Active at +$" + DoubleToString(InpGoldTrailTrigger_USD, 2)) : "OFF (Trades reach full TP!)") + "\n";
   text += " Strategies    : H4 S&R Zone + H1 Trend Pullback\n";
   text += "=====================================================\n";

   Comment(text);
}
//+------------------------------------------------------------------+
