import React from 'react';
import Card from '../../components/common/Card';
import { formatPercent } from '../../utils/formatters';

export const MonthlyReturns = () => {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  const years = [
    {
      year: 2026,
      returns: [4.2, 2.8, 5.1, 3.4, -1.2, 6.0, 4.8, 2.1, 3.9, 5.5, 4.1, 3.8],
      total: 44.5
    },
    {
      year: 2025,
      returns: [2.5, 3.1, -0.8, 4.2, 5.0, 1.9, 3.8, -1.5, 4.4, 2.9, 3.7, 4.1],
      total: 33.3
    }
  ];

  const getCellColor = (val) => {
    if (val > 4) return 'bg-emerald-500/25 text-emerald-300 font-bold';
    if (val > 0) return 'bg-emerald-500/10 text-emerald-400';
    if (val < -3) return 'bg-rose-500/25 text-rose-300 font-bold';
    if (val < 0) return 'bg-rose-500/10 text-rose-400';
    return 'bg-slate-900 text-slate-400';
  };

  return (
    <Card title="Monthly Return Heatmap (%)" subtitle="Audited periodic algorithmic yield">
      <div className="overflow-x-auto">
        <table className="w-full text-center text-xs font-mono border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400">
              <th className="py-2 px-3 text-left font-sans font-semibold">Year</th>
              {months.map((m) => (
                <th key={m} className="py-2 px-2 font-semibold">
                  {m}
                </th>
              ))}
              <th className="py-2 px-3 font-sans font-bold text-cyan-400">YTD</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {years.map((y) => (
              <tr key={y.year}>
                <td className="py-2.5 px-3 text-left font-bold text-slate-200">{y.year}</td>
                {y.returns.map((val, idx) => (
                  <td key={idx} className="p-1">
                    <div className={`py-1.5 px-1 rounded ${getCellColor(val)}`}>
                      {formatPercent(val)}
                    </div>
                  </td>
                ))}
                <td className="py-2.5 px-3 font-bold text-cyan-400 bg-cyan-950/20">
                  {formatPercent(y.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

export default MonthlyReturns;
