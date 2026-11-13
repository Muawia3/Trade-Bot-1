import React from 'react';

export const StatusBadge = ({ type = 'mode', value = 'PAPER', size = 'md', pulse = false }) => {
  if (type === 'mode') {
    const valUpper = String(value || '').toUpperCase();
    const isLive = valUpper === 'LIVE';
    const isPaper = valUpper === 'PAPER';
    const isDemo = valUpper === 'DEMO';

    let badgeStyle = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
    let dotStyle = 'bg-cyan-400';

    if (isLive) {
      badgeStyle = 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-lg shadow-rose-950/50';
      dotStyle = 'bg-rose-500 animate-pulse';
    } else if (isPaper) {
      badgeStyle = 'bg-amber-500/10 text-amber-300 border-amber-500/30';
      dotStyle = 'bg-amber-400';
    } else if (isDemo) {
      badgeStyle = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
      dotStyle = 'bg-emerald-400';
    }

    return (
      <div
        className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase border transition-all ${badgeStyle}`}
      >
        <span className={`w-2 h-2 rounded-full ${dotStyle}`} />
        <span>{valUpper} TRADING</span>
      </div>
    );
  }

  if (type === 'connection') {
    const valUpper = String(value || '').toUpperCase();
    const isOnline = valUpper === 'ONLINE' || valUpper === 'CONNECTED';
    return (
      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-900/60 border border-slate-800 text-slate-300">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            isOnline ? 'bg-emerald-400' : 'bg-rose-500'
          } ${pulse ? 'animate-ping' : ''}`}
        />
        <span>{valUpper}</span>
      </div>
    );
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
      {value}
    </span>
  );
};

export default StatusBadge;
