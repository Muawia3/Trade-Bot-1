import React from 'react';
import Card from '../../components/common/Card';
import { formatPrice } from '../../utils/formatters';

export const OrderBook = ({ symbol = 'XAUUSD', currentPrice = 2650.50 }) => {
  const isGold = symbol.toUpperCase().includes('XAU');
  const step = isGold ? 0.30 : 0.00015;

  const asks = [
    { price: currentPrice + step * 4, size: 14.5, total: 42.1 },
    { price: currentPrice + step * 3, size: 8.2, total: 27.6 },
    { price: currentPrice + step * 2, size: 12.0, total: 19.4 },
    { price: currentPrice + step * 1, size: 7.4, total: 7.4 }
  ];

  const bids = [
    { price: currentPrice - step * 1, size: 6.8, total: 6.8 },
    { price: currentPrice - step * 2, size: 11.2, total: 18.0 },
    { price: currentPrice - step * 3, size: 9.5, total: 27.5 },
    { price: currentPrice - step * 4, size: 15.1, total: 42.6 }
  ];

  return (
    <Card title="Depth of Market (DOM)" subtitle="Live institutional order book depth" className="h-full">
      <div className="font-mono text-xs space-y-1">
        {/* Asks (Sell Orders - Red) */}
        <div className="space-y-0.5">
          {asks.map((ask, idx) => (
            <div
              key={idx}
              className="relative flex items-center justify-between px-2 py-1 rounded bg-rose-500/5 hover:bg-rose-500/10 text-rose-300"
            >
              <span className="font-semibold">{formatPrice(ask.price, symbol)}</span>
              <span className="text-slate-400">{ask.size.toFixed(1)} lots</span>
              <div
                className="absolute right-0 top-0 bottom-0 bg-rose-500/10 -z-0 pointer-events-none rounded"
                style={{ width: `${Math.min(100, (ask.total / 45) * 100)}%` }}
              />
            </div>
          ))}
        </div>

        {/* Spread separator */}
        <div className="py-2 my-1 text-center font-bold text-slate-300 bg-slate-900/90 rounded border border-slate-800 flex items-center justify-around">
          <span className="text-[11px] text-slate-500 uppercase font-sans">Spread</span>
          <span className="text-cyan-400">
            {isGold ? `${(step * 10).toFixed(1)} pts` : `${(step * 10000).toFixed(1)} pips`}
          </span>
          <span className="text-xs text-slate-100">{formatPrice(currentPrice, symbol)}</span>
        </div>

        {/* Bids (Buy Orders - Green) */}
        <div className="space-y-0.5">
          {bids.map((bid, idx) => (
            <div
              key={idx}
              className="relative flex items-center justify-between px-2 py-1 rounded bg-emerald-500/5 hover:bg-emerald-500/10 text-emerald-300"
            >
              <span className="font-semibold">{formatPrice(bid.price, symbol)}</span>
              <span className="text-slate-400">{bid.size.toFixed(1)} lots</span>
              <div
                className="absolute right-0 top-0 bottom-0 bg-emerald-500/10 -z-0 pointer-events-none rounded"
                style={{ width: `${Math.min(100, (bid.total / 45) * 100)}%` }}
              />
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
};

export default OrderBook;
