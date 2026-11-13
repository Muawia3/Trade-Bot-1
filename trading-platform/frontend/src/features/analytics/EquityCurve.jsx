import React from 'react';
import Card from '../../components/common/Card';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from 'recharts';
import { formatCurrency } from '../../utils/formatters';

export const EquityCurve = ({ data = [], height = 320 }) => {
  // Generate sample equity curve if empty
  const defaultData = [
    { date: 'Day 1', equity: 10000, balance: 10000 },
    { date: 'Day 5', equity: 10240, balance: 10180 },
    { date: 'Day 10', equity: 10190, balance: 10220 },
    { date: 'Day 15', equity: 10650, balance: 10500 },
    { date: 'Day 20', equity: 10820, balance: 10740 },
    { date: 'Day 25', equity: 10710, balance: 10800 },
    { date: 'Day 30', equity: 11150, balance: 11020 },
    { date: 'Day 35', equity: 11480, balance: 11390 },
    { date: 'Day 40', equity: 11920, balance: 11800 },
    { date: 'Day 45', equity: 12250, balance: 12150 },
    { date: 'Day 50', equity: 12425, balance: 12380 }
  ];

  const chartData = data.length > 0 ? data : defaultData;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="p-3 bg-slate-900 border border-slate-700 rounded-xl shadow-xl font-mono text-xs space-y-1">
          <p className="font-sans font-bold text-slate-300">{label}</p>
          <p className="text-emerald-400">Equity: {formatCurrency(payload[0].value)}</p>
          {payload[1] && <p className="text-cyan-400">Balance: {formatCurrency(payload[1].value)}</p>}
        </div>
      );
    }
    return null;
  };

  return (
    <Card title="Portfolio Equity Growth Curve" subtitle="Dynamic capital growth vs realized balance baseline">
      <div style={{ width: '100%', height: height }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis
              stroke="#64748b"
              tick={{ fill: '#64748b', fontSize: 11 }}
              domain={['auto', 'auto']}
              tickFormatter={(v) => `$${v}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
              formatter={(val) => <span className="text-slate-300 font-sans">{val}</span>}
            />
            <Line
              type="monotone"
              dataKey="equity"
              name="Portfolio Equity"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={{ r: 3, fill: '#10b981' }}
              activeDot={{ r: 6 }}
            />
            <Line
              type="stepAfter"
              dataKey="balance"
              name="Account Balance"
              stroke="#38bdf8"
              strokeWidth={1.8}
              strokeDasharray="4 4"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};

export default EquityCurve;
