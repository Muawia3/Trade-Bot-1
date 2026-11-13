import React, { useState } from 'react';
import Card from '../../components/common/Card';
import Table from '../../components/common/Table';
import { formatCurrency, formatPrice, formatDate, getPnlBg } from '../../utils/formatters';

export const TradeHistory = ({ history = [] }) => {
  const [filterSymbol, setFilterSymbol] = useState('ALL');

  const defaultHistory = [
    {
      id: 'TRD-1099',
      ticket: 8919421,
      symbol: 'XAUUSD',
      type: 'BUY',
      lots: 0.25,
      openPrice: 2634.20,
      closePrice: 2648.80,
      pnl: 365.00,
      openTime: new Date(Date.now() - 3600000 * 8).toISOString(),
      closeTime: new Date(Date.now() - 3600000 * 2).toISOString(),
      reason: 'Take Profit Hit',
      strategy: 'Breakout Gold Alpha'
    },
    {
      id: 'TRD-1098',
      ticket: 8918230,
      symbol: 'EURUSD',
      type: 'BUY',
      lots: 0.40,
      openPrice: 1.08250,
      closePrice: 1.08510,
      pnl: 104.00,
      openTime: new Date(Date.now() - 3600000 * 18).toISOString(),
      closeTime: new Date(Date.now() - 3600000 * 10).toISOString(),
      reason: 'Take Profit Hit',
      strategy: 'London Scalper EUR'
    },
    {
      id: 'TRD-1097',
      ticket: 8917890,
      symbol: 'XAUUSD',
      type: 'SELL',
      lots: 0.15,
      openPrice: 2645.00,
      closePrice: 2652.00,
      pnl: -105.00,
      openTime: new Date(Date.now() - 86400000 * 1.5).toISOString(),
      closeTime: new Date(Date.now() - 86400000 * 1.1).toISOString(),
      reason: 'Stop Loss Hit',
      strategy: 'Mean Reversion Gold'
    },
    {
      id: 'TRD-1096',
      ticket: 8916540,
      symbol: 'GBPUSD',
      type: 'BUY',
      lots: 0.30,
      openPrice: 1.29400,
      closePrice: 1.29820,
      pnl: 126.00,
      openTime: new Date(Date.now() - 86400000 * 2).toISOString(),
      closeTime: new Date(Date.now() - 86400000 * 1.8).toISOString(),
      reason: 'Trailing Stop Hit',
      strategy: 'Breakout Gold Alpha'
    }
  ];

  const rawData = history.length > 0 ? history : defaultHistory;
  const filteredData = filterSymbol === 'ALL'
    ? rawData
    : rawData.filter((t) => t.symbol === filterSymbol);

  const columns = [
    {
      label: 'Ticket',
      key: 'ticket',
      render: (val, row) => `#${val || row.id}`
    },
    {
      label: 'Symbol & Side',
      key: 'symbol',
      render: (val, row) => (
        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-200">{val}</span>
          <span
            className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
              row.type === 'BUY' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
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
      label: 'Open Price',
      key: 'openPrice',
      render: (val, row) => formatPrice(val, row.symbol)
    },
    {
      label: 'Close Price',
      key: 'closePrice',
      render: (val, row) => formatPrice(val, row.symbol)
    },
    {
      label: 'Outcome Reason',
      key: 'reason',
      render: (val) => <span className="text-slate-400 font-sans text-xs">{val}</span>
    },
    {
      label: 'Net P/L',
      key: 'pnl',
      align: 'right',
      render: (val) => (
        <span className={`px-2 py-0.5 rounded font-bold ${getPnlBg(val)}`}>
          {val >= 0 ? `+${formatCurrency(val)}` : formatCurrency(val)}
        </span>
      )
    },
    {
      label: 'Closed At',
      key: 'closeTime',
      align: 'right',
      render: (val) => formatDate(val, true)
    }
  ];

  return (
    <Card
      title="Closed Trade Journal"
      subtitle="Comprehensive history of all realized operations"
      actions={
        <div className="flex items-center gap-2">
          <select
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-300 text-xs rounded-lg px-2.5 py-1 font-mono focus:outline-none"
          >
            <option value="ALL">All Instruments</option>
            <option value="XAUUSD">XAUUSD</option>
            <option value="EURUSD">EURUSD</option>
            <option value="GBPUSD">GBPUSD</option>
          </select>
        </div>
      }
    >
      <Table columns={columns} data={filteredData} emptyMessage="No closed trades match filter." />
    </Card>
  );
};

export default TradeHistory;
