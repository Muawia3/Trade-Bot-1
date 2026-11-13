import React from 'react';
import Card from '../../components/common/Card';
import { formatCurrency, formatPercent } from '../../utils/formatters';

export const PerformanceMetrics = ({ metrics = {} }) => {
  const data = {
    totalTrades: metrics.totalTrades || 342,
    winRate: metrics.winRate || 68.4,
    profitFactor: metrics.profitFactor || 2.14,
    sharpeRatio: metrics.sharpeRatio || 1.95,
    maxDrawdown: metrics.maxDrawdown || 4.8,
    netProfit: metrics.netProfit || 4280.50,
    avgWin: metrics.avgWin || 184.20,
    avgLoss: metrics.avgLoss || 98.40,
    expectancy: metrics.expectancy || 1.25,
    ...metrics
  };

  const metricCards = [
    { label: 'Net Cumulative Profit', value: `+${formatCurrency(data.netProfit)}`, color: 'text-emerald-400' },
    { label: 'Win Rate', value: formatPercent(data.winRate), color: 'text-cyan-400' },
    { label: 'Profit Factor', value: data.profitFactor.toFixed(2), color: 'text-slate-100' },
    { label: 'Sharpe Ratio', value: data.sharpeRatio.toFixed(2), color: 'text-indigo-400' },
    { label: 'Max Peak Drawdown', value: `-${data.maxDrawdown}%`, color: 'text-rose-400' },
    { label: 'Total Executions', value: `${data.totalTrades} Orders`, color: 'text-slate-200' },
    { label: 'Average Win', value: `+${formatCurrency(data.avgWin)}`, color: 'text-emerald-400' },
    { label: 'Average Loss', value: `-${formatCurrency(data.avgLoss)}`, color: 'text-rose-400' }
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {metricCards.map((item, idx) => (
        <Card key={idx} className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-[10px] uppercase font-sans font-semibold tracking-wider text-slate-400 block mb-1">
            {item.label}
          </span>
          <span className={`text-xl font-bold font-mono ${item.color}`}>{item.value}</span>
        </Card>
      ))}
    </div>
  );
};

export default PerformanceMetrics;
