import React from 'react';
import { TIMEFRAMES, SYMBOLS } from '../../utils/constants';

export const ChartToolbar = ({
  activeSymbol = 'XAUUSD',
  onSelectSymbol,
  activeTimeframe = 'M15',
  onSelectTimeframe,
  showIndicators,
  onToggleIndicators
}) => {
  const instruments = [
    { id: 'XAUUSD', label: 'Gold (XAU/USD)', icon: '🥇' },
    { id: 'EURUSD', label: 'EUR/USD', icon: '💶' },
    { id: 'GBPUSD', label: 'GBP/USD', icon: '💷' },
    { id: 'USDJPY', label: 'USD/JPY', icon: '💴' }
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-900/80 border border-slate-800 rounded-xl mb-3">
      {/* Symbol Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
        {instruments.map((inst) => (
          <button
            key={inst.id}
            onClick={() => onSelectSymbol(inst.id)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
              activeSymbol === inst.id
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <span>{inst.icon}</span>
            <span>{inst.id}</span>
          </button>
        ))}
      </div>

      {/* Timeframe & Indicators */}
      <div className="flex items-center gap-3">
        {/* Timeframe selector */}
        <div className="flex items-center bg-slate-950/70 p-1 rounded-lg border border-slate-800/80 font-mono text-xs">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              onClick={() => onSelectTimeframe(tf.value)}
              className={`px-2.5 py-1 rounded transition ${
                activeTimeframe === tf.value
                  ? 'bg-cyan-600 text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>

        {/* Indicators toggle */}
        <button
          onClick={onToggleIndicators}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
            showIndicators
              ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
              : 'bg-slate-800 text-slate-400 border-slate-700'
          }`}
        >
          EMA 20 {showIndicators ? 'ON' : 'OFF'}
        </button>
      </div>
    </div>
  );
};

export default ChartToolbar;
