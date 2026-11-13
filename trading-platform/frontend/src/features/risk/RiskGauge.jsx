import React from 'react';
import Card from '../../components/common/Card';

export const RiskGauge = ({ score = 28 }) => {
  // Score 0 - 100
  let statusText = 'LOW RISK';
  let colorClass = 'text-emerald-400';
  let barColor = 'bg-emerald-500';

  if (score > 75) {
    statusText = 'CRITICAL RISK';
    colorClass = 'text-rose-400';
    barColor = 'bg-rose-500';
  } else if (score > 50) {
    statusText = 'ELEVATED RISK';
    colorClass = 'text-amber-400';
    barColor = 'bg-amber-500';
  } else if (score > 30) {
    statusText = 'MODERATE RISK';
    colorClass = 'text-cyan-400';
    barColor = 'bg-cyan-500';
  }

  return (
    <Card title="Current Risk Exposure Meter" subtitle="Real-time account margin & correlation safety index">
      <div className="flex flex-col items-center justify-center p-4">
        {/* Gauge Center Display */}
        <div className="relative w-44 h-24 overflow-hidden flex items-end justify-center mb-3">
          {/* Half circle track */}
          <div className="absolute top-0 w-44 h-44 rounded-full border-[12px] border-slate-800" />
          {/* Active progress arc indicator */}
          <div
            className={`absolute top-0 w-44 h-44 rounded-full border-[12px] border-transparent border-t-cyan-500 border-l-cyan-500 transition-transform duration-700 ease-out`}
            style={{ transform: `rotate(${-45 + (score / 100) * 180}deg)` }}
          />
          <div className="text-center z-10 -mb-1">
            <span className={`text-3xl font-black font-mono block ${colorClass}`}>{score}</span>
            <span className="text-[10px] text-slate-500 uppercase tracking-widest font-sans font-bold">
              / 100 Index
            </span>
          </div>
        </div>

        <div className="text-center space-y-1">
          <span className={`text-xs font-bold uppercase tracking-wider ${colorClass}`}>{statusText}</span>
          <p className="text-[11px] text-slate-400 max-w-xs font-sans">
            Account margin is well within conservative guidelines. Circuit breaker triggers at 80/100.
          </p>
        </div>

        {/* Bar */}
        <div className="w-full bg-slate-900 h-2 rounded-full mt-4 overflow-hidden border border-slate-800">
          <div className={`h-full ${barColor} transition-all duration-500`} style={{ width: `${score}%` }} />
        </div>
      </div>
    </Card>
  );
};

export default RiskGauge;
