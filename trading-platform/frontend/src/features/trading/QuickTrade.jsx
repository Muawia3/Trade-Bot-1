import React, { useState } from 'react';
import Card from '../../components/common/Card';
import { formatCurrency, formatPrice } from '../../utils/formatters';
import { useTrades } from '../../hooks/useTrades';
import { useTradingContext } from '../../context/TradingContext';

export const QuickTrade = ({ defaultSymbol = 'XAUUSD', currentPrice = 2650.50 }) => {
  const { executeTrade, submitting } = useTrades();
  const { account, tradingMode } = useTradingContext();

  const [symbol, setSymbol] = useState(defaultSymbol);
  const [orderType, setOrderType] = useState('MARKET');
  const [lots, setLots] = useState(0.10);
  const [slPips, setSlPips] = useState(50);
  const [tpPips, setTpPips] = useState(100);
  const [statusMsg, setStatusMsg] = useState(null);

  const isGold = symbol.toUpperCase().includes('XAU');
  const pipValue = isGold ? 10.0 : 10.0; // standard 1 lot value per pip/point in USD approx

  // Estimated Risk calculation
  const estDollarRisk = lots * slPips * (isGold ? 1.0 : 1.0);
  const riskPercent = ((estDollarRisk / (account.equity || 10000)) * 100).toFixed(2);
  const estDollarReward = lots * tpPips * (isGold ? 1.0 : 1.0);
  const rrRatio = (tpPips / (slPips || 1)).toFixed(1);

  const handleTrade = async (side) => {
    setStatusMsg(null);
    const orderPayload = {
      symbol,
      type: side,
      lots: Number(lots),
      sl_pips: Number(slPips),
      tp_pips: Number(tpPips),
      order_type: orderType,
      mode: tradingMode
    };

    const res = await executeTrade(orderPayload);
    if (res.success) {
      setStatusMsg({ type: 'success', text: `Order submitted: ${side} ${lots} ${symbol}` });
    } else {
      setStatusMsg({ type: 'error', text: res.error || 'Execution failed' });
    }
  };

  return (
    <Card
      title="Instant Order Terminal"
      subtitle={`Executing in ${tradingMode} trading mode`}
      badge={
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
          Broker: Direct MT5
        </span>
      }
    >
      <div className="space-y-4">
        {statusMsg && (
          <div
            className={`p-2.5 rounded-lg text-xs font-semibold ${
              statusMsg.type === 'success'
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
            }`}
          >
            {statusMsg.text}
          </div>
        )}

        {/* Symbol and Order Type */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Instrument</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="XAUUSD">XAUUSD (Gold)</option>
              <option value="EURUSD">EURUSD</option>
              <option value="GBPUSD">GBPUSD</option>
              <option value="USDJPY">USDJPY</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Execution Type</label>
            <select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="MARKET">Market Execution</option>
              <option value="LIMIT">Limit Order</option>
              <option value="STOP">Stop Order</option>
            </select>
          </div>
        </div>

        {/* Volume Lots & Presets */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <label className="text-[11px] font-semibold text-slate-400">Position Volume (Lots)</label>
            <span className="text-[10px] text-slate-500 font-mono">Max limit: 5.00</span>
          </div>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max="10.0"
            value={lots}
            onChange={(e) => setLots(Math.max(0.01, parseFloat(e.target.value) || 0.01))}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-cyan-500"
          />
          <div className="flex items-center gap-1.5 mt-2">
            {[0.01, 0.05, 0.10, 0.25, 0.50, 1.0].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setLots(preset)}
                className={`flex-1 py-1 text-[10px] font-mono rounded border transition ${
                  lots === preset
                    ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800'
                }`}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        {/* Stop Loss & Take Profit in Pips */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-rose-400 block mb-1">Stop Loss (Pips)</label>
            <input
              type="number"
              value={slPips}
              onChange={(e) => setSlPips(Math.max(5, parseInt(e.target.value) || 0))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-rose-300 focus:outline-none focus:border-rose-500"
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-emerald-400 block mb-1">Take Profit (Pips)</label>
            <input
              type="number"
              value={tpPips}
              onChange={(e) => setTpPips(Math.max(5, parseInt(e.target.value) || 0))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-emerald-300 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        {/* Live Risk Matrix */}
        <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800/80 font-mono text-[11px] space-y-1">
          <div className="flex justify-between">
            <span className="text-slate-400">Calculated Risk:</span>
            <span className="text-rose-400 font-bold">{formatCurrency(estDollarRisk)} ({riskPercent}%)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Target Reward:</span>
            <span className="text-emerald-400 font-bold">{formatCurrency(estDollarReward)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Risk/Reward Ratio:</span>
            <span className="text-cyan-400 font-bold">1 : {rrRatio}</span>
          </div>
        </div>

        {/* Direct Action Execution Buttons */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            onClick={() => handleTrade('SELL')}
            disabled={submitting}
            className="py-3 px-4 bg-gradient-to-r from-rose-700 to-rose-600 hover:from-rose-600 hover:to-rose-500 text-white font-bold text-xs uppercase tracking-wider rounded-xl shadow-lg shadow-rose-950/40 transition disabled:opacity-50"
          >
            SELL / SHORT
          </button>
          <button
            onClick={() => handleTrade('BUY')}
            disabled={submitting}
            className="py-3 px-4 bg-gradient-to-r from-emerald-700 to-emerald-600 hover:from-emerald-600 hover:to-emerald-500 text-white font-bold text-xs uppercase tracking-wider rounded-xl shadow-lg shadow-emerald-950/40 transition disabled:opacity-50"
          >
            BUY / LONG
          </button>
        </div>
      </div>
    </Card>
  );
};

export default QuickTrade;
