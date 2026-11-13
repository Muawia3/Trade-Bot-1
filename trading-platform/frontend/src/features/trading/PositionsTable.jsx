import React, { useState } from 'react';
import Card from '../../components/common/Card';
import Table from '../../components/common/Table';
import { formatCurrency, formatPrice, formatDate, getPnlColor, getPnlBg } from '../../utils/formatters';
import { useTradingContext } from '../../context/TradingContext';

export const PositionsTable = ({ onModifyPosition }) => {
  const { positions, closePosition } = useTradingContext();
  const [closingId, setClosingId] = useState(null);

  const handleClose = async (posId) => {
    setClosingId(posId);
    try {
      await closePosition(posId);
    } finally {
      setClosingId(null);
    }
  };

  const columns = [
    {
      label: 'Ticket / ID',
      key: 'ticket',
      render: (val, row) => (
        <div>
          <span className="font-bold text-slate-200 block">#{val || row.id}</span>
          <span className="text-[10px] text-slate-500 font-sans">{row.strategy || 'Manual Trade'}</span>
        </div>
      )
    },
    {
      label: 'Instrument',
      key: 'symbol',
      render: (val, row) => (
        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-100">{val}</span>
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
              row.type === 'BUY'
                ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                : 'text-rose-400 bg-rose-500/10 border border-rose-500/20'
            }`}
          >
            {row.type}
          </span>
        </div>
      )
    },
    {
      label: 'Lots',
      key: 'lots',
      render: (val) => `${val} L`
    },
    {
      label: 'Open Price',
      key: 'openPrice',
      render: (val, row) => formatPrice(val, row.symbol)
    },
    {
      label: 'Current Price',
      key: 'currentPrice',
      render: (val, row) => formatPrice(val, row.symbol)
    },
    {
      label: 'SL / TP',
      key: 'sl',
      render: (val, row) => (
        <div className="text-[11px]">
          <span className="text-rose-400 block">SL: {row.sl ? formatPrice(row.sl, row.symbol) : 'None'}</span>
          <span className="text-emerald-400 block">TP: {row.tp ? formatPrice(row.tp, row.symbol) : 'None'}</span>
        </div>
      )
    },
    {
      label: 'Floating P/L',
      key: 'pnl',
      align: 'right',
      render: (val) => (
        <span className={`px-2 py-1 rounded font-bold ${getPnlBg(val)}`}>
          {val >= 0 ? `+${formatCurrency(val)}` : formatCurrency(val)}
        </span>
      )
    },
    {
      label: 'Actions',
      key: 'id',
      align: 'right',
      render: (val, row) => (
        <div className="flex items-center justify-end gap-1.5">
          <button
            onClick={() => onModifyPosition && onModifyPosition(row)}
            className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] font-sans transition"
          >
            Modify
          </button>
          <button
            onClick={() => handleClose(row.id || row.ticket)}
            disabled={closingId === (row.id || row.ticket)}
            className="px-2 py-1 bg-rose-600/20 hover:bg-rose-600 text-rose-300 hover:text-white rounded text-[11px] font-sans font-semibold border border-rose-500/30 transition disabled:opacity-50"
          >
            {closingId === (row.id || row.ticket) ? 'Closing...' : 'Close'}
          </button>
        </div>
      )
    }
  ];

  return (
    <Card
      title="Open Market Positions"
      subtitle={`${positions.length} active exposure position(s)`}
      badge={
        positions.length > 0 && (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-300">
            {positions.length} LIVE
          </span>
        )
      }
    >
      <Table
        columns={columns}
        data={positions}
        emptyMessage="No open positions currently active. All capital is protected."
      />
    </Card>
  );
};

export default PositionsTable;
