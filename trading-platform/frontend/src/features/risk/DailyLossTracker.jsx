import React from 'react';
import Card from '../../components/common/Card';
import { formatCurrency, formatPercent } from '../../utils/formatters';

export const DailyLossTracker = ({
  currentLoss = 145.20,
  maxDailyLoss = 500.00,
  currentDrawdown = 2.1,
  maxDrawdown = 10.0
}) => {
  const lossPercent = Math.min(100, (currentLoss / maxDailyLoss) * 100);
  const remainingBudget = Math.max(0, maxDailyLoss - currentLoss);
  const ddPercent = Math.min(100, (currentDrawdown / maxDrawdown) * 100);

  return (
    <Card title="Circuit Breakers & Daily Buffers" subtitle="Hard safety stop counters">
      <div className="space-y-4 font-mono text-xs">
        {/* Daily Loss Tracker */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center text-slate-300">
            <span className="font-sans font-semibold">Today's Realized Drawdown:</span>
            <span className="font-bold text-rose-400">
              {formatCurrency(currentLoss)} / {formatCurrency(maxDailyLoss)}
            </span>
          </div>
          <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800">
            <div
              className={`h-full ${lossPercent > 80 ? 'bg-rose-500' : lossPercent > 50 ? 'bg-amber-500' : 'bg-cyan-500'}`}
              style={{ width: `${lossPercent}%` }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-slate-500">
            <span>Remaining Daily Buffer: <strong className="text-emerald-400">{formatCurrency(remainingBudget)}</strong></span>
            <span>{lossPercent.toFixed(1)}% consumed</span>
          </div>
        </div>

        {/* Global Max Drawdown Tracker */}
        <div className="space-y-1.5 pt-2 border-t border-slate-800/80">
          <div className="flex justify-between items-center text-slate-300">
            <span className="font-sans font-semibold">Total Portfolio Drawdown:</span>
            <span className="font-bold text-amber-400">
              {currentDrawdown.toFixed(1)}% / {maxDrawdown.toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800">
            <div
              className={`h-full ${ddPercent > 75 ? 'bg-rose-500' : 'bg-indigo-500'}`}
              style={{ width: `${ddPercent}%` }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-slate-500">
            <span>Safety Margin to Cutoff: <strong className="text-slate-300">{(maxDrawdown - currentDrawdown).toFixed(1)}%</strong></span>
            <span>Status: <strong className="text-emerald-400 uppercase">SAFE</strong></span>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default DailyLossTracker;
