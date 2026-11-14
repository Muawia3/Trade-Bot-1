//+------------------------------------------------------------------+
//|                                     Exness_AutoTrader_EA.mq5     |
//|               Professional Auto-Trading Bot for MT5 / Exness     |
//|                                  Instruments: XAUUSD & EURUSD    |
//+------------------------------------------------------------------+
#property copyright "Exness AutoTrader"
#property link      "https://www.exness.com"
#property version   "1.30"
#property description "Automated Quantitative Forex & Gold Trading Robot for Exness MT5."
#property description "Features: H4 S&R + M15/M5 Engulfing (1:2 R:R), EMA Cascades, RSI Filter, and Trailing Stop."

#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Input Parameters ---
input group "=== Risk & Money Management ==="
input bool     InpUseFixedLot       = false;       // Use Fixed Lot Size (false = Dynamic Risk Calculation)
input double   InpFixedLotSize      = 0.01;        // Fixed Lot Size (e.g. 0.01)
input double   InpRiskPercent       = 1.0;         // % Risk per Trade (if Fixed Lot = false)
input double   InpMinLotLimit       = 0.01;        // Minimum Allowed Lot
input double   InpMaxLotLimit       = 0.50;        // Maximum Allowed Lot
input int      InpMaxOpenPositions  = 1;           // Max Open Positions per Symbol
input ulong    InpMagicNumber       = 998877;      // Unique Magic Number

input group "=== Strategy 1: H4 Support/Resistance + Engulfing (1:2 R:R) ==="
input bool            InpUseH4_SNR         = true;        // Enable H4 S&R + Engulfing Strategy
input ENUM_TIMEFRAMES InpEntryTF           = PERIOD_M5;   // Confirmation Timeframe (M5 or M15)
input int             InpH4Lookback        = 40;          // H4 Lookback Bars
input double          InpH4TolerancePct    = 0.25;        // S&R Zone Tolerance %
input bool            InpDynamicMarketSL   = true;        // Dynamic Market Structure SL (Candle Low/High)
input double          InpRiskRewardRatio   = 2.0;         // Risk to Reward Ratio (2.0 = 1:2)
input double          InpStructureBufferGold = 0.50;      // Gold SL Buffer in USD ($0.50)
input double          InpStructureBufferPips = 2.0;       // Forex SL Buffer in Pips (2 pips)
input double          InpGoldMinSL_USD     = 1.5;         // Gold Min SL in USD
input double          InpGoldMaxSL_USD     = 8.0;         // Gold Max SL in USD
input double          InpForexMinSL_Pips   = 10.0;        // Forex Min SL in Pips
input double          InpForexMaxSL_Pips   = 45.0;        // Forex Max SL in Pips
input double          InpGoldSL_USD        = 4.0;         // Fallback Gold Stop Loss in USD ($4.00)
input double          InpForexSL_Pips      = 20.0;        // Fallback Forex Stop Loss in Pips (20 pips)

input group "=== Strategy 2: Indicator Trend Cascade ==="
input int      InpFastEMAPeriod     = 20;          // Fast EMA Period
input int      InpSlowEMAPeriod     = 50;          // Slow EMA Period
input int      InpTrendEMAPeriod    = 200;         // Trend Baseline EMA Period
input int      InpRSIPeriod         = 14;          // RSI Period
input double   InpRSIOverbought     = 70.0;        // RSI Overbought Level
input double   InpRSIOversold       = 30.0;        // RSI Oversold Level
input int      InpATRPeriod         = 14;          // ATR Period (Volatility)

input group "=== Trailing Stop ==="
input bool     InpUseTrailingStop   = true;        // Enable Trailing Stop
input double   InpTrailingStartPips = 15.0;        // Pips in profit before Trailing activates
input double   InpTrailingStepPips  = 5.0;         // Trailing distance in pips

//--- Global Handles & Objects ---
CTrade         m_trade;
CSymbolInfo    m_symbol;
CPositionInfo  m_position;
CAccountInfo   m_account;

int            h_ema_fast  = INVALID_HANDLE;
int            h_ema_slow  = INVALID_HANDLE;
int            h_ema_trend = INVALID_HANDLE;
int            h_rsi       = INVALID_HANDLE;
int            h_atr       = INVALID_HANDLE;

datetime       last_bar_time = 0;
string         g_status_msg  = "Initializing...";

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

   h_ema_fast  = iMA(_Symbol, _Period, InpFastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_slow  = iMA(_Symbol, _Period, InpSlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_trend = iMA(_Symbol, _Period, InpTrendEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi       = iRSI(_Symbol, _Period, InpRSIPeriod, PRICE_CLOSE);
   h_atr       = iATR(_Symbol, _Period, InpATRPeriod);

   Print("=================================================");
   Print("  EXNESS AUTO-TRADER EA STARTED SUCCESSFULLY");
   Print("  Symbol    : ", _Symbol);
   Print("  Account   : ", m_account.Login(), " (", m_account.Currency(), ")");
   Print("  Balance   : $", DoubleToString(m_account.Balance(), 2));
   Print("  H4 S&R 1:2: ", (InpUseH4_SNR ? "ENABLED (SL=$4, TP=$8)" : "DISABLED"));
   Print("=================================================");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_ema_fast);
   IndicatorRelease(h_ema_slow);
   IndicatorRelease(h_ema_trend);
   IndicatorRelease(h_rsi);
   IndicatorRelease(h_atr);
   Comment("");
   Print("Exness Auto-Trader EA stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Find H4 Support and Resistance Levels                            |
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
//| Check Candlestick Engulfing Patterns                             |
//+------------------------------------------------------------------+
bool CheckBullishEngulfing(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return false;
   bool prev_red = (rates[1].close < rates[1].open);
   bool curr_green = (rates[0].close > rates[0].open);
   bool engulfs = (rates[0].open <= rates[1].close * 1.0005) && (rates[0].close >= rates[1].open * 0.9995);
   return (prev_red && curr_green && engulfs);
}

bool CheckBearishEngulfing(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return false;
   bool prev_green = (rates[1].close > rates[1].open);
   bool curr_red = (rates[0].close < rates[0].open);
   bool engulfs = (rates[0].open >= rates[1].close * 0.9995) && (rates[0].close <= rates[1].open * 1.0005);
   return (prev_green && curr_red && engulfs);
}

double GetEngulfingPatternLow(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return 0.0;
   return MathMin(rates[0].low, rates[1].low);
}

double GetEngulfingPatternHigh(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 1, 2, rates) < 2) return 0.0;
   return MathMax(rates[0].high, rates[1].high);
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

   if(InpUseTrailingStop)
      ApplyTrailingStop(bid, ask);

   double cur_price = bid;
   int open_pos     = CountOpenPositions();
   double balance   = m_account.Balance();

   if(balance <= 0.0)
   {
      g_status_msg = "⚠️ ACCOUNT BALANCE IS $0.00! Please deposit Demo funds to trade.";
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, open_pos);
      return;
   }

   if(open_pos >= InpMaxOpenPositions)
   {
      g_status_msg = "Position currently OPEN. Managing with 1:2 R:R Trailing Stop.";
      UpdateChartDashboard(balance, cur_price, 0, 0, 0, open_pos);
      return;
   }

   datetime current_bar_time = iTime(_Symbol, _Period, 0);

   // -------------------------------------------------------------
   // STRATEGY 1: H4 SUPPORT/RESISTANCE + M15/M5 ENGULFING (1:2 R:R)
   // -------------------------------------------------------------
   if(InpUseH4_SNR)
   {
      double supports[], resistances[];
      GetH4SupportResistance(supports, resistances);

      double tol = InpH4TolerancePct / 100.0;
      double near_support = 0.0;
      double near_resistance = 0.0;

      for(int i = 0; i < ArraySize(supports); i++)
      {
         if(MathAbs(cur_price - supports[i]) / cur_price <= tol)
         {
            near_support = supports[i];
            break;
         }
      }

      for(int i = 0; i < ArraySize(resistances); i++)
      {
         if(MathAbs(cur_price - resistances[i]) / cur_price <= tol)
         {
            near_resistance = resistances[i];
            break;
         }
      }

      bool is_gold = (StringFind(_Symbol, "XAU") >= 0);
      int stop_level_points = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double min_stop_dist = MathMax(stop_level_points * _Point, (ask - bid) * 2.0);

      // Support + Bullish Engulfing -> BUY
      if(near_support > 0.0 && CheckBullishEngulfing(InpEntryTF))
      {
         g_status_msg = "🎯 H4 Support + Bullish Engulfing! Executing BUY (Dynamic 1:2 R:R)...";
         if(current_bar_time != last_bar_time)
         {
            last_bar_time = current_bar_time;
            double sl_dist = 0.0;
            if(InpDynamicMarketSL)
            {
               double pat_low = GetEngulfingPatternLow(InpEntryTF);
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
               sl_dist = is_gold ? InpGoldSL_USD : (InpForexSL_Pips * _Point * 10.0);
            }
            sl_dist = MathMax(sl_dist, min_stop_dist);
            double tp_dist = sl_dist * InpRiskRewardRatio;

            double sl = NormalizeDouble(ask - sl_dist, _Digits);
            double tp = NormalizeDouble(ask + tp_dist, _Digits);
            double lot = CalculateLot(sl_dist);

            if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "H4_SNR_BUY_1to2"))
            {
               Print("✅ [H4 S&R BUY 1:2 EXECUTED] Lot: ", lot, " | Price: ", ask, " | SL: ", sl, " | TP: ", tp);
               g_status_msg = "H4 S&R BUY Executed (SL: " + DoubleToString(sl_dist, _Digits) + ", TP: " + DoubleToString(tp_dist, _Digits) + ")!";
            }
         }
         UpdateChartDashboard(balance, cur_price, 0, 0, 0, open_pos);
         return;
      }

      // Resistance + Bearish Engulfing -> SELL
      if(near_resistance > 0.0 && CheckBearishEngulfing(InpEntryTF))
      {
         g_status_msg = "🎯 H4 Resistance + Bearish Engulfing! Executing SELL (Dynamic 1:2 R:R)...";
         if(current_bar_time != last_bar_time)
         {
            last_bar_time = current_bar_time;
            double sl_dist = 0.0;
            if(InpDynamicMarketSL)
            {
               double pat_high = GetEngulfingPatternHigh(InpEntryTF);
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
               sl_dist = is_gold ? InpGoldSL_USD : (InpForexSL_Pips * _Point * 10.0);
            }
            sl_dist = MathMax(sl_dist, min_stop_dist);
            double tp_dist = sl_dist * InpRiskRewardRatio;

            double sl = NormalizeDouble(bid + sl_dist, _Digits);
            double tp = NormalizeDouble(bid - tp_dist, _Digits);
            double lot = CalculateLot(sl_dist);

            if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "H4_SNR_SELL_1to2"))
            {
               Print("✅ [H4 S&R SELL 1:2 EXECUTED] Lot: ", lot, " | Price: ", bid, " | SL: ", sl, " | TP: ", tp);
               g_status_msg = "H4 S&R SELL Executed (SL: " + DoubleToString(sl_dist, _Digits) + ", TP: " + DoubleToString(tp_dist, _Digits) + ")!";
            }
         }
         UpdateChartDashboard(balance, cur_price, 0, 0, 0, open_pos);
         return;
      }
   }

   // -------------------------------------------------------------
   // STRATEGY 2: REGULAR EMA + RSI MOMENTUM
   // -------------------------------------------------------------
   double ema_fast[2], ema_slow[2], rsi[2], atr[1];
   if(CopyBuffer(h_ema_fast, 0, 0, 2, ema_fast) < 2) return;
   if(CopyBuffer(h_ema_slow, 0, 0, 2, ema_slow) < 2) return;
   if(CopyBuffer(h_rsi, 0, 0, 2, rsi) < 2) return;
   if(CopyBuffer(h_atr, 0, 0, 1, atr) < 1) return;

   double cur_rsi  = rsi[0];
   double cur_fast = ema_fast[0];
   double cur_slow = ema_slow[0];
   double cur_atr  = atr[0];

   bool buy_condition  = (ema_fast[1] > ema_slow[1]) && (cur_price > ema_fast[0]) && (rsi[0] >= 45.0 && rsi[0] <= 68.0);
   bool sell_condition = (ema_fast[1] < ema_slow[1]) && (cur_price < ema_fast[0]) && (rsi[0] >= 32.0 && rsi[0] <= 55.0);

   int stop_level_points = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double min_stop_dist = MathMax(stop_level_points * _Point, (ask - bid) * 2.0);

   if(buy_condition && current_bar_time != last_bar_time)
   {
      last_bar_time = current_bar_time;
      double sl_dist = MathMax(cur_atr * 1.5, min_stop_dist);
      double tp_dist = sl_dist * 2.0; // 1:2 Risk to Reward
      double sl = NormalizeDouble(ask - sl_dist, _Digits);
      double tp = NormalizeDouble(ask + tp_dist, _Digits);
      double lot = CalculateLot(sl_dist);

      if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "ExnessAutoEA_BUY"))
         g_status_msg = "Trend BUY Trade Executed (1:2 R:R)!";
   }
   else if(sell_condition && current_bar_time != last_bar_time)
   {
      last_bar_time = current_bar_time;
      double sl_dist = MathMax(cur_atr * 1.5, min_stop_dist);
      double tp_dist = sl_dist * 2.0; // 1:2 Risk to Reward
      double sl = NormalizeDouble(bid + sl_dist, _Digits);
      double tp = NormalizeDouble(bid - tp_dist, _Digits);
      double lot = CalculateLot(sl_dist);

      if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "ExnessAutoEA_SELL"))
         g_status_msg = "Trend SELL Trade Executed (1:2 R:R)!";
   }
   else
   {
      g_status_msg = "H4 S&R Active. Monitoring H4 Key Levels & M5 Engulfing patterns...";
   }

   UpdateChartDashboard(balance, cur_price, cur_rsi, cur_fast, cur_slow, open_pos);
}

//+------------------------------------------------------------------+
//| Update Chart On-Screen Dashboard                                 |
//+------------------------------------------------------------------+
void UpdateChartDashboard(double balance, double price, double rsi, double fast, double slow, int open_pos)
{
   string text = "";
   text += "=====================================================\n";
   text += "       EXNESS AUTOTRADER BOT (H4 S&R + 1:2 R:R)      \n";
   text += "=====================================================\n";
   text += "  Symbol       : " + _Symbol + " (" + EnumToString(_Period) + ")\n";
   text += "  Balance      : $" + DoubleToString(balance, 2) + " " + m_account.Currency() + "\n";
   text += "  Equity       : $" + DoubleToString(m_account.Equity(), 2) + "\n";
   text += "  Leverage     : 1:" + IntegerToString(m_account.Leverage()) + "\n";
   text += "-----------------------------------------------------\n";
   text += "  Current Price: " + DoubleToString(price, _Digits) + "\n";
   text += "  Strategy     : H4 S&R + M15/M5 Engulfing (1:2 R:R)\n";
   text += "  Gold Target  : SL = $4.00 | TP = $8.00 (Exact 1:2)\n";
   text += "  Open Trades  : " + IntegerToString(open_pos) + " / " + IntegerToString(InpMaxOpenPositions) + "\n";
   text += "-----------------------------------------------------\n";
   text += "  BOT STATUS   : " + g_status_msg + "\n";
   text += "=====================================================\n";

   Comment(text);
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
//| Dynamic Trailing Stop to Lock In Profits                         |
//+------------------------------------------------------------------+
void ApplyTrailingStop(double bid, double ask)
{
   double point = _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() != _Symbol || m_position.Magic() != InpMagicNumber)
            continue;

         ulong ticket = m_position.Ticket();
         double open_price = m_position.PriceOpen();
         double current_sl = m_position.StopLoss();
         double current_tp = m_position.TakeProfit();

         if(m_position.PositionType() == POSITION_TYPE_BUY)
         {
            double profit_pips = (bid - open_price) / (point * 10);
            if(profit_pips >= InpTrailingStartPips)
            {
               double new_sl = NormalizeDouble(bid - (InpTrailingStepPips * point * 10), _Digits);
               if(new_sl > current_sl && new_sl > open_price)
               {
                  m_trade.PositionModify(ticket, new_sl, current_tp);
                  Print("📈 [TRAILING STOP] BUY Ticket #", ticket, " SL adjusted to: ", new_sl);
               }
            }
         }
         else if(m_position.PositionType() == POSITION_TYPE_SELL)
         {
            double profit_pips = (open_price - ask) / (point * 10);
            if(profit_pips >= InpTrailingStartPips)
            {
               double new_sl = NormalizeDouble(ask + (InpTrailingStepPips * point * 10), _Digits);
               if((current_sl == 0.0 || new_sl < current_sl) && new_sl < open_price)
               {
                  m_trade.PositionModify(ticket, new_sl, current_tp);
                  Print("📉 [TRAILING STOP] SELL Ticket #", ticket, " SL adjusted to: ", new_sl);
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
