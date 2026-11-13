import React, { useState } from 'react';
import Card from '../../components/common/Card';

export const RiskConfig = ({ onSave }) => {
  const [params, setParams] = useState({
    defaultRiskPercent: 1.0,
    maxDailyLossPercent: 5.0,
    maxOpenPositions: 5,
    maxDrawdownPercent: 10.0,
    killSwitchEnabled: true,
    trailingStopDefault: true,
    newsFilterEnabled: true
  });
  const [saved, setSaved] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSave) onSave(params);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <Card
      title="Global Risk Engine Policy"
      subtitle="Server-side enforced parameters that cannot be bypassed by AI models"
    >
      <form onSubmit={handleSubmit} className="space-y-4 font-mono text-xs">
        {saved && (
          <div className="p-3 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 rounded-lg font-sans">
            ✓ Risk parameters saved and synchronized with MT5 safety bridge.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-slate-400 block mb-1">Max Daily Loss Limit (%)</label>
            <input
              type="number"
              step="0.5"
              value={params.maxDailyLossPercent}
              onChange={(e) => setParams({ ...params, maxDailyLossPercent: parseFloat(e.target.value) })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-rose-400"
            />
            <span className="text-[10px] text-slate-500 font-sans mt-0.5 block">
              Trading halts automatically when daily loss reaches this limit.
            </span>
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Max Portfolio Drawdown (%)</label>
            <input
              type="number"
              step="0.5"
              value={params.maxDrawdownPercent}
              onChange={(e) => setParams({ ...params, maxDrawdownPercent: parseFloat(e.target.value) })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-rose-400"
            />
            <span className="text-[10px] text-slate-500 font-sans mt-0.5 block">
              Global breaker threshold from high-water mark.
            </span>
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Max Concurrent Positions</label>
            <input
              type="number"
              value={params.maxOpenPositions}
              onChange={(e) => setParams({ ...params, maxOpenPositions: parseInt(e.target.value) })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-cyan-400"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Default Risk Per Trade (%)</label>
            <input
              type="number"
              step="0.1"
              value={params.defaultRiskPercent}
              onChange={(e) => setParams({ ...params, defaultRiskPercent: parseFloat(e.target.value) })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-cyan-400"
            />
          </div>
        </div>

        {/* Checkbox toggles */}
        <div className="pt-2 border-t border-slate-800 space-y-2 font-sans">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={params.killSwitchEnabled}
              onChange={(e) => setParams({ ...params, killSwitchEnabled: e.target.checked })}
              className="rounded bg-slate-900 border-slate-700 text-cyan-600 focus:ring-0"
            />
            <span className="text-slate-300">Automated Circuit Breaker (Kill Switch) Active</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={params.newsFilterEnabled}
              onChange={(e) => setParams({ ...params, newsFilterEnabled: e.target.checked })}
              className="rounded bg-slate-900 border-slate-700 text-cyan-600 focus:ring-0"
            />
            <span className="text-slate-300">Pause execution 30 mins before & after High Impact Red News (NFP/FOMC)</span>
          </label>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-slate-800">
          <button
            type="button"
            className="px-4 py-2 bg-rose-600/20 hover:bg-rose-600 text-rose-300 hover:text-white rounded-lg text-xs font-bold border border-rose-500/40 transition"
          >
            🚨 Emergency Flatten All Positions
          </button>
          <button
            type="submit"
            className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-bold shadow-md transition"
          >
            Save Policy Settings
          </button>
        </div>
      </form>
    </Card>
  );
};

export default RiskConfig;
