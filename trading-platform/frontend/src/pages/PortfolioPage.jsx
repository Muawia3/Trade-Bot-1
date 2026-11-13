import React from 'react';
import Card from '../components/common/Card';
import EquityCurve from '../features/analytics/EquityCurve';
import { formatCurrency, formatPercent } from '../utils/formatters';
import { useTradingContext } from '../context/TradingContext';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie
} from 'recharts';

export const PortfolioPage = () => {
  const { account, positions } = useTradingContext();

  const allocationData = [
    { name: 'XAUUSD (Gold)', value: 55, color: '#f59e0b' },
    { name: 'EURUSD', value: 30, color: '#38bdf8' },
    { name: 'GBPUSD', value: 15, color: '#818cf8' }
  ];

  const dailyPnlData = [
    { day: 'Mon', pnl: 240 },
    { day: 'Tue', pnl: 410 },
    { day: 'Wed', pnl: -120 },
    { day: 'Thu', pnl: 380 },
    { day: 'Fri', pnl: 290 },
    { day: 'Mon', pnl: 180 },
    { day: 'Tue', pnl: -85 },
    { day: 'Wed', pnl: 320 }
  ];

  return (
    <div className="space-y-6">
      {/* Portfolio Header Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold block">
            Total Portfolio Equity
          </span>
          <span className="text-2xl font-black font-mono text-slate-100 mt-1 block">
            {formatCurrency(account.equity)}
          </span>
          <span className="text-[11px] text-emerald-400 font-mono mt-1 block">
            +24.25% All-Time Return
          </span>
        </Card>

        <Card className="p-4">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold block">
            Floating Net P/L
          </span>
          <span className="text-2xl font-black font-mono text-emerald-400 mt-1 block">
            +$294.00
          </span>
          <span className="text-[11px] text-slate-400 font-mono mt-1 block">
            {positions.length} Active Positions Exposed
          </span>
        </Card>

        <Card className="p-4">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold block">
            Current Drawdown
          </span>
          <span className="text-2xl font-black font-mono text-cyan-400 mt-1 block">
            2.1%
          </span>
          <span className="text-[11px] text-slate-400 font-mono mt-1 block">
            Max permitted: 10.0%
          </span>
        </Card>
      </div>

      {/* Equity Curve Chart */}
      <EquityCurve height={340} />

      {/* Middle: Asset Allocation & Daily P/L */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Allocation Pie Chart */}
        <Card title="Capital Allocation by Symbol" subtitle="Percentage of risk exposure per currency/metal pair">
          <div className="h-64 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={allocationData}
                  cx="50%"
                  cy="50%"
                  innerRadius={65}
                  outerRadius={90}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {allocationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(val) => [`${val}%`, 'Allocation']}
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-6 text-xs font-mono pt-2">
            {allocationData.map((item) => (
              <div key={item.name} className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-slate-300">{item.name} ({item.value}%)</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Daily PnL Bar Chart */}
        <Card title="Daily Realized P/L ($)" subtitle="Day-by-day cash flow consistency">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dailyPnlData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <XAxis dataKey="day" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
                <Tooltip
                  formatter={(val) => [formatCurrency(val), 'Net P/L']}
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                />
                <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                  {dailyPnlData.map((entry, index) => (
                    <Cell key={`bar-${index}`} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default PortfolioPage;
