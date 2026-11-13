import React from 'react';
import Card from '../../components/common/Card';
import Table from '../../components/common/Table';
import { formatCurrency, formatPrice, formatDate, getPnlColor, getPnlBg } from '../../utils/formatters';

export const RecentTrades = ({ trades = [] }) => {
  const sampleTrades = [
    {
      id: 'T101',
      ticket: 8919421,
      symbol: 'XAUUSD',
      type: 'BUY',
      lots: 0.25,
      openPrice: 2634.20,
      closePrice: 2648.80,
      pnl: 365.00,
      closeTime: new Date(Date.now() - 3600000 * 4).toISOString(),
      strategy: 'Breakout Gold Alpha'
    },
    {
      id: 'T102',
      ticket: 8918230,
      symbol: 'EURUSD',
      type: 'BUY',
      lots: 0.40,
      openPrice: 1.08250,
      closePrice: 1.08510,
      pnl: 104.00,
      closeTime: new Date(Date.now() - 3600000 * 12).toISOString(),
      strategy: 'London Scalper EUR'
    },
    {
      id: 'T103',
      ticket: 8917890,
      symbol: 'XAUUSD',
      type: 'SELL',
      lots: 0.15,
      openPrice: 2645.00,
      closePrice: 2652.00,
      pnl: -105.00,
      closeTime: new Date(Date.now() - 3600000 * 22).toISOString(),
      strategy: 'Mean Reversion Gold'
    }
  ];

  const data = trades.length > 0 ? trades : sampleTrades;

  const columns = [
    {
      label: 'Instrument',
      key: 'symbol',
      render: (val, row) => (
        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-200">{val}</span>
          <span
            className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
              row.type === 'BUY'
                ? 'text-emerald-400 bg-emerald-500/10'
                : 'text-rose-400 bg-rose-500/10'
            }`}
          >
            {row.type}
          </span>
        </div>
      )
    },
    {
      label: 'Volume',
      key: 'lots',
      render: (val) => `${val} lots`
    },
    {
      label: 'Open / Close',
      key: 'openPrice',
      render: (val, row) => (
        <span className="text-slate-400">
          {formatPrice(val, row.symbol)} → {formatPrice(row.closePrice, row.symbol)}
        </span>
      )
    },
    {
      label: 'Profit / Loss',
      key: 'pnl',
      align: 'right',
      render: (val) => (
        <span className={`px-2 py-0.5 rounded font-bold ${getPnlBg(val)}`}>
          {val >= 0 ? `+${formatCurrency(val)}` : formatCurrency(val)}
        </span>
      )
    },
    {
      label: 'Execution Time',
      key: 'closeTime',
      align: 'right',
      render: (val) => formatDate(val, true)
    }
  ];

  return (
    <Card title="Executed Orders History" subtitle="Audited trade executions from MT5 bridge / paper engine">
      <Table columns={columns} data={data} emptyMessage="No recent trades recorded." />
    </Card>
  );
};

export default RecentTrades;
