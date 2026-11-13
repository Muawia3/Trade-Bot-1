import React, { useState, useEffect } from 'react';
import { useTradingContext } from '../../context/TradingContext';
import { useWebSocketContext } from '../../context/WebSocketContext';
import StatusBadge from './StatusBadge';
import { formatCurrency, getPnlColor } from '../../utils/formatters';
import { TRADING_MODES } from '../../utils/constants';

export const Header = () => {
  const { tradingMode, switchMode, account, connections, positions } = useTradingContext();
  const { isConnected } = useWebSocketContext();
  const [currentTime, setCurrentTime] = useState(new Date().toUTCString().slice(17, 25));

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toUTCString().slice(17, 25));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const totalPnl = positions.reduce((acc, pos) => acc + (pos.pnl || 0), 0);
  const currentMode = String(tradingMode || '').toLowerCase();

  return (
    <header className="h-16 border-b border-slate-800/80 bg-[#0a0f1d]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Left side: System status & Mode */}
      <div className="flex items-center gap-4">
        {/* Prominent Trading Mode Badge */}
        <div className="flex items-center gap-2">
          <StatusBadge type="mode" value={tradingMode} />
          
          {/* Mode Switch Selector */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs font-semibold">
            <button
              onClick={() => switchMode(TRADING_MODES.PAPER)}
              className={`px-2.5 py-1 rounded transition-all ${
                currentMode === TRADING_MODES.PAPER
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Paper
            </button>
            <button
              onClick={() => switchMode(TRADING_MODES.DEMO)}
              className={`px-2.5 py-1 rounded transition-all ${
                currentMode === TRADING_MODES.DEMO
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Demo
            </button>
            <button
              onClick={() => switchMode(TRADING_MODES.LIVE)}
              className={`px-2.5 py-1 rounded transition-all ${
                currentMode === TRADING_MODES.LIVE
                  ? 'bg-rose-500/30 text-rose-300 border border-rose-500/60 shadow-sm animate-pulse-subtle'
                  : 'text-slate-400 hover:text-rose-400'
              }`}
            >
              Live
            </button>
          </div>
        </div>

        {/* Bridge & WS Indicators */}
        <div className="hidden lg:flex items-center gap-2 border-l border-slate-800/80 pl-4">
          <span className="text-[10px] text-slate-500 uppercase font-mono tracking-wider">MT5:</span>
          <StatusBadge type="connection" value={connections.mt5} />

          <span className="text-[10px] text-slate-500 uppercase font-mono tracking-wider ml-1">Feed:</span>
          <StatusBadge type="connection" value={isConnected ? 'ONLINE' : 'DISCONNECTED'} />
        </div>
      </div>

      {/* Right side: Real-time Account Metrics & Clock */}
      <div className="flex items-center gap-6 font-mono">
        {/* Live Metrics */}
        <div className="hidden md:flex items-center gap-5 text-xs">
          <div className="flex flex-col text-right">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-sans">Balance</span>
            <span className="font-bold text-slate-200">{formatCurrency(account.balance)}</span>
          </div>

          <div className="flex flex-col text-right">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-sans">Equity</span>
            <span className="font-bold text-slate-100">{formatCurrency(account.equity)}</span>
          </div>

          <div className="flex flex-col text-right">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-sans">Open P/L</span>
            <span className={`font-bold ${getPnlColor(totalPnl)}`}>
              {totalPnl >= 0 ? `+${formatCurrency(totalPnl)}` : formatCurrency(totalPnl)}
            </span>
          </div>
        </div>

        {/* UTC Clock & Server Info */}
        <div className="flex items-center gap-3 border-l border-slate-800/80 pl-4">
          <div className="text-right">
            <div className="text-xs font-semibold text-slate-300">{currentTime} UTC</div>
            <div className="text-[10px] text-emerald-400 uppercase tracking-wider">London / NY Active</div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
