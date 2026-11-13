import React from 'react';
import Card from '../../components/common/Card';

export const SpreadMonitor = ({ symbol = 'XAUUSD', spread = 0.30 }) => {
  const isGold = symbol.toUpperCase().includes('XAU');

  const sessions = [
    { name: 'London', status: 'OPEN', hours: '08:00 - 16:30 GMT', active: true },
    { name: 'New York', status: 'OPEN', hours: '13:00 - 21:00 GMT', active: true },
    { name: 'Tokyo', status: 'CLOSED', hours: '00:00 - 09:00 GMT', active: false },
    { name: 'Sydney', status: 'CLOSED', hours: '22:00 - 07:00 GMT', active: false }
  ];

  return (
    <Card title="Market Session & Liquidity" subtitle="Live interbank conditions">
      <div className="space-y-4 text-xs font-mono">
        {/* Spread Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <span className="text-[10px] text-slate-400 uppercase font-sans block">Current Spread</span>
            <span className="text-lg font-bold text-cyan-400">
              {isGold ? `${(spread * 10).toFixed(1)} pts` : `${(spread * 10000).toFixed(1)} pips`}
            </span>
          </div>
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <span className="text-[10px] text-slate-400 uppercase font-sans block">Volatility</span>
            <span className="text-lg font-bold text-amber-400">Normal (ATR 18.4)</span>
          </div>
        </div>

        {/* Sessions */}
        <div className="space-y-1.5 pt-1">
          <span className="text-[10px] text-slate-400 uppercase font-sans block mb-1">Global Forex Sessions</span>
          {sessions.map((s, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-2 rounded-lg bg-slate-950/40 border border-slate-800/60"
            >
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${s.active ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
                <span className={`font-semibold ${s.active ? 'text-slate-100' : 'text-slate-500'}`}>{s.name}</span>
              </div>
              <span className="text-[10px] text-slate-400">{s.hours}</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                  s.active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800 text-slate-500'
                }`}
              >
                {s.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
};

export default SpreadMonitor;
