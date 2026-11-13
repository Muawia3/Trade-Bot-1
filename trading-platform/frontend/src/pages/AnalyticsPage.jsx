import React from 'react';
import PerformanceMetrics from '../features/analytics/PerformanceMetrics';
import DrawdownChart from '../features/analytics/DrawdownChart';
import MonthlyReturns from '../features/analytics/MonthlyReturns';
import TradeDistribution from '../features/analytics/TradeDistribution';
import Card from '../components/common/Card';
import Table from '../components/common/Table';
import { formatCurrency, formatPercent } from '../utils/formatters';

export const AnalyticsPage = () => {
  const strategyComparison = [
    { name: 'Breakout Gold Alpha', trades: 148, winRate: 68.5, profitFactor: 2.18, netProfit: 2450.00, sharpe: 2.1 },
    { name: 'London Scalper EUR', trades: 122, winRate: 72.1, profitFactor: 1.95, netProfit: 1380.50, sharpe: 1.9 },
    { name: 'Mean Reversion Bollinger', trades: 72, winRate: 64.0, profitFactor: 1.72, netProfit: 450.00, sharpe: 1.4 }
  ];

  const columns = [
    { label: 'Strategy Model', key: 'name', render: (val) => <strong className="text-slate-100">{val}</strong> },
    { label: 'Executed Trades', key: 'trades' },
    { label: 'Win Rate', key: 'winRate', render: (val) => <span className="text-emerald-400 font-bold">{formatPercent(val)}</span> },
    { label: 'Profit Factor', key: 'profitFactor', render: (val) => val.toFixed(2) },
    { label: 'Sharpe', key: 'sharpe', render: (val) => val.toFixed(2) },
    {
      label: 'Net Realized Profit',
      key: 'netProfit',
      align: 'right',
      render: (val) => <span className="text-emerald-400 font-bold">+{formatCurrency(val)}</span>
    }
  ];

  const tradeOutliers = [
    { label: 'Best Single Win', val: '+$640.00 (XAUUSD 1.0L)', color: 'text-emerald-400' },
    { label: 'Worst Single Loss', val: '-$210.00 (EURUSD 0.5L)', color: 'text-rose-400' },
    { label: 'Consecutive Wins Streak', val: '8 Trades', color: 'text-cyan-400' },
    { label: 'Consecutive Losses Streak', val: '3 Trades', color: 'text-amber-400' }
  ];

  return (
    <div className="space-y-6">
      {/* Metrics Cards */}
      <PerformanceMetrics />

      {/* Extreme Outliers Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {tradeOutliers.map((item, idx) => (
          <Card key={idx} className="p-3 bg-slate-900/60 border-slate-800">
            <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block mb-0.5">
              {item.label}
            </span>
            <span className={`text-sm font-bold font-mono ${item.color}`}>{item.val}</span>
          </Card>
        ))}
      </div>

      {/* Drawdown & Distribution Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DrawdownChart height={240} />
        <TradeDistribution height={240} />
      </div>

      {/* Monthly Returns Heatmap */}
      <MonthlyReturns />

      {/* Quantitative Strategy Comparison Table */}
      <Card title="Strategy Model Comparison Breakdown" subtitle="Benchmarking individual algorithmic systems">
        <Table columns={columns} data={strategyComparison} />
      </Card>
    </div>
  );
};

export default AnalyticsPage;
