import React from 'react';
import Card from '../../components/common/Card';
import { formatPercent } from '../../utils/formatters';

export const StrategyCard = ({ strategy, onToggle, onConfigure }) => {
  const isEnabled = strategy.enabled;

  return (
    <Card
      className="flex flex-col justify-between hover:border-slate-700 transition"
      headerClassName="pb-2"
      title={strategy.name}
      badge={
        <span
          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
            isEnabled
              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
              : 'bg-slate-800 text-slate-500 border border-slate-700'
          }`}
        >
          {isEnabled ? 'Active Running' : 'Disabled'}
        </span>
      }
      actions={
        <div className="flex items-center gap-2">
          {/* Toggle Switch */}
          <button
            onClick={() => onToggle && onToggle(strategy.id, !isEnabled)}
            className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ease-in-out ${
              isEnabled ? 'bg-cyan-600' : 'bg-slate-700'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-200 ease-in-out ${
                isEnabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <p className="text-xs text-slate-300 leading-relaxed min-h-[38px]">{strategy.description}</p>

        {/* Target Instruments & Timeframe */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
          <span className="text-slate-500">Pairs:</span>
          {strategy.symbols?.map((sym) => (
            <span key={sym} className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-slate-200 font-bold">
              {sym}
            </span>
          ))}
          <span className="px-2 py-0.5 bg-slate-800/80 rounded text-cyan-400 font-bold ml-auto">
            {strategy.timeframe}
          </span>
        </div>

        {/* Backtested Metrics */}
        <div className="grid grid-cols-3 gap-2 p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 font-mono text-center">
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">Win Rate</span>
            <span className="text-xs font-bold text-emerald-400">{formatPercent(strategy.winRate)}</span>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">Profit Factor</span>
            <span className="text-xs font-bold text-slate-100">{strategy.profitFactor || '1.85'}</span>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">Max Drawdown</span>
            <span className="text-xs font-bold text-rose-400">-{strategy.maxDrawdown || '4.2%'}</span>
          </div>
        </div>

        {/* Configure Button */}
        <div className="pt-1">
          <button
            onClick={() => onConfigure && onConfigure(strategy)}
            className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition flex items-center justify-center gap-2"
          >
            <span>⚙️ Configure Strategy Parameters</span>
          </button>
        </div>
      </div>
    </Card>
  );
};

export default StrategyCard;
