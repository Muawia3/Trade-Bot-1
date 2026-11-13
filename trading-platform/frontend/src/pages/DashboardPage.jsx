import React from 'react';
import DashboardCards from '../features/dashboard/DashboardCards';
import MiniChart from '../features/dashboard/MiniChart';
import ActiveSignals from '../features/dashboard/ActiveSignals';
import RecentTrades from '../features/dashboard/RecentTrades';
import RiskGauge from '../features/risk/RiskGauge';
import Card from '../components/common/Card';
import StatusBadge from '../components/common/StatusBadge';
import { useTradingContext } from '../context/TradingContext';
import { useWebSocketContext } from '../context/WebSocketContext';

export const DashboardPage = () => {
  const { tradingMode, connections, riskMetrics, account } = useTradingContext();
  const { latestPrices } = useWebSocketContext();

  return (
    <div className="space-y-6">
      {/* Top Banner: Mode & Server Connectivity */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div className="flex items-center gap-3">
          <StatusBadge type="mode" value={tradingMode} />
          <div className="text-xs text-slate-300">
            <span className="text-slate-500">Connected Terminal:</span>{' '}
            <strong className="text-slate-100">{account.server || 'MetaQuotes-Demo'}</strong> (Account #{account.accountNumber})
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">MT5 Bridge:</span>
            <StatusBadge type="connection" value={connections.mt5} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">PostgreSQL DB:</span>
            <StatusBadge type="connection" value={connections.database} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">AI Engine:</span>
            <StatusBadge type="connection" value={connections.aiModel} />
          </div>
        </div>
      </div>

      {/* Primary Stat Metric Cards */}
      <DashboardCards />

      {/* Mini Charts for Primary Instruments: XAUUSD & EURUSD */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-4" variant="default">
          <MiniChart
            symbol="XAUUSD"
            price={latestPrices.XAUUSD?.bid || 2650.60}
            change={latestPrices.XAUUSD?.change24h || 1.15}
            height={190}
          />
        </Card>
        <Card className="p-4" variant="default">
          <MiniChart
            symbol="EURUSD"
            price={latestPrices.EURUSD?.bid || 1.08456}
            change={latestPrices.EURUSD?.change24h || -0.22}
            height={190}
          />
        </Card>
      </div>

      {/* Middle Section: Active Signals & Risk Gauge */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ActiveSignals />
        </div>
        <div className="lg:col-span-1">
          <RiskGauge score={riskMetrics.riskScore || 28} />
        </div>
      </div>

      {/* Bottom Section: Recent Executed Trades */}
      <div>
        <RecentTrades />
      </div>
    </div>
  );
};

export default DashboardPage;
