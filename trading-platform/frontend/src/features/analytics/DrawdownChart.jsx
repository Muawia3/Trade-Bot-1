import React from 'react';
import Card from '../../components/common/Card';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from 'recharts';

export const DrawdownChart = ({ data = [], height = 220 }) => {
  const defaultData = [
    { date: 'W1', drawdown: 0.0 },
    { date: 'W2', drawdown: -1.2 },
    { date: 'W3', drawdown: -0.5 },
    { date: 'W4', drawdown: 0.0 },
    { date: 'W5', drawdown: -3.8 },
    { date: 'W6', drawdown: -2.1 },
    { date: 'W7', drawdown: -0.4 },
    { date: 'W8', drawdown: 0.0 },
    { date: 'W9', drawdown: -1.5 },
    { date: 'W10', drawdown: 0.0 }
  ];

  const chartData = data.length > 0 ? data : defaultData;

  return (
    <Card title="Underwater Drawdown (%)" subtitle="Peak-to-valley risk depth over time">
      <div style={{ width: '100%', height: height }}>
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="drawdownGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis
              stroke="#64748b"
              tick={{ fill: '#64748b', fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              formatter={(v) => [`${v}%`, 'Drawdown']}
              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
            />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ef4444"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#drawdownGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};

export default DrawdownChart;
