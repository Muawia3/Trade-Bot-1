import React from 'react';
import Card from '../../components/common/Card';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell
} from 'recharts';

export const TradeDistribution = ({ height = 220 }) => {
  const distributionData = [
    { bucket: '< -$200', count: 4, isLoss: true },
    { bucket: '-$200 to -$100', count: 12, isLoss: true },
    { bucket: '-$100 to $0', count: 28, isLoss: true },
    { bucket: '$0 to $100', count: 46, isLoss: false },
    { bucket: '$100 to $200', count: 68, isLoss: false },
    { bucket: '$200 to $300', count: 34, isLoss: false },
    { bucket: '> $300', count: 18, isLoss: false }
  ];

  return (
    <Card title="P/L Outcome Distribution" subtitle="Trade frequency by realized profit/loss brackets">
      <div style={{ width: '100%', height: height }}>
        <ResponsiveContainer>
          <BarChart data={distributionData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="bucket" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 10 }} />
            <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
            <Tooltip
              formatter={(val) => [`${val} Trades`, 'Frequency']}
              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {distributionData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.isLoss ? '#ef4444' : '#10b981'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};

export default TradeDistribution;
