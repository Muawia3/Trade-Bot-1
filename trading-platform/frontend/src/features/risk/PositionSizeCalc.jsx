import React, { useState } from 'react';
import Card from '../../components/common/Card';
import { formatCurrency, formatLot } from '../../utils/formatters';
import { useTradingContext } from '../../context/TradingContext';

export const PositionSizeCalc = () => {
  const { account } = useTradingContext();

  const [symbol, setSymbol] = useState('XAUUSD');
  const [riskPercent, setRiskPercent] = useState(1.0);
  const [stopLossPips, setStopLossPips] = useState(50);

  const equity = account.equity || 10000;
  const isGold = symbol.toUpperCase().includes('XAU');

  // Calculation:
  // Risk Amount ($) = Equity * (RiskPercent / 100)
  // For Gold: 1 lot = 100 oz. 1 pip (0.10) is $10. 1 pt (0.01) is $1.
  // Standard Forex: 1 lot = 100,000 units. 1 pip is $10.
  const riskAmount = equity * (riskPercent / 100);
  const pipValuePerLot = 10; // $10 per pip per 1 standard lot
  const calculatedLots = stopLossPips > 0 ? riskAmount / (stopLossPips * pipValuePerLot) : 0.01;
  const safeLot = Math.min(Math.max(0.01, calculatedLots), 50.0);

  return (
    <Card title="Position Sizing Calculator" subtitle="Mathematical risk & lot size optimization formula">
      <div className="space-y-4 font-mono text-xs">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-slate-400 block mb-1">Instrument</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-slate-200"
            >
              <option value="XAUUSD">XAUUSD (Gold)</option>
              <option value="EURUSD">EURUSD</option>
              <option value="GBPUSD">GBPUSD</option>
              <option value="USDJPY">USDJPY</option>
            </select>
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Risk Percentage (%)</label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="10.0"
              value={riskPercent}
              onChange={(e) => setRiskPercent(parseFloat(e.target.value) || 0.1)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-cyan-400"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1">SL Distance (Pips)</label>
            <input
              type="number"
              min="1"
              value={stopLossPips}
              onChange={(e) => setStopLossPips(parseInt(e.target.value) || 1)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-rose-400"
            />
          </div>
        </div>

        {/* Calculated Output Box */}
        <div className="p-4 bg-slate-950/70 rounded-xl border border-slate-800 grid grid-cols-2 gap-4">
          <div>
            <span className="text-[10px] text-slate-500 uppercase block font-sans">Allowed Risk Capital</span>
            <span className="text-lg font-bold text-slate-200">{formatCurrency(riskAmount)}</span>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 uppercase block font-sans">Recommended Lot Size</span>
            <span className="text-2xl font-black text-cyan-400">{formatLot(safeLot)} Lots</span>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default PositionSizeCalc;
