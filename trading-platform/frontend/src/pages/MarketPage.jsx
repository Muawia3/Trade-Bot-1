import React, { useState } from 'react';
import ChartToolbar from '../features/market/ChartToolbar';
import PriceChart from '../features/market/PriceChart';
import OrderBook from '../features/market/OrderBook';
import SpreadMonitor from '../features/market/SpreadMonitor';
import PriceDisplay from '../components/common/PriceDisplay';
import { useMarketData } from '../hooks/useMarketData';
import LoadingSpinner from '../components/common/LoadingSpinner';

export const MarketPage = () => {
  const [activeSymbol, setActiveSymbol] = useState('XAUUSD');
  const [activeTimeframe, setActiveTimeframe] = useState('M15');
  const [showIndicators, setShowIndicators] = useState(true);

  const { currentTick, candles, loading } = useMarketData(activeSymbol, activeTimeframe);

  return (
    <div className="space-y-4">
      {/* Header bar with Symbol Quote details */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-slate-100">{activeSymbol}</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                CFD Spot
              </span>
            </div>
            <p className="text-xs text-slate-400 font-sans">
              {activeSymbol === 'XAUUSD' ? 'Gold vs US Dollar (Troy Ounce)' : 'Euro vs US Dollar'}
            </p>
          </div>

          <div className="border-l border-slate-800 pl-4">
            <PriceDisplay
              price={currentTick.bid}
              symbol={activeSymbol}
              size="lg"
              showChange
              change={currentTick.change24h || 0.42}
            />
          </div>
        </div>

        {/* Bid / Ask Box */}
        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="p-2 px-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-right">
            <span className="text-[10px] text-slate-400 block uppercase font-sans">Bid (Sell)</span>
            <span className="font-bold text-sm">{currentTick.bid}</span>
          </div>

          <div className="p-2 px-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-right">
            <span className="text-[10px] text-slate-400 block uppercase font-sans">Ask (Buy)</span>
            <span className="font-bold text-sm">{currentTick.ask}</span>
          </div>
        </div>
      </div>

      {/* Toolbar Controls */}
      <ChartToolbar
        activeSymbol={activeSymbol}
        onSelectSymbol={setActiveSymbol}
        activeTimeframe={activeTimeframe}
        onSelectTimeframe={setActiveTimeframe}
        showIndicators={showIndicators}
        onToggleIndicators={() => setShowIndicators(!showIndicators)}
      />

      {/* Main Chart and Order Depth Section */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          {loading && candles.length === 0 ? (
            <div className="h-[520px] flex items-center justify-center bg-slate-900/60 rounded-xl border border-slate-800">
              <LoadingSpinner text={`Loading ${activeSymbol} Candlesticks...`} />
            </div>
          ) : (
            <PriceChart
              symbol={activeSymbol}
              candles={candles}
              timeframe={activeTimeframe}
              height={520}
              showIndicators={showIndicators}
            />
          )}
        </div>

        <div className="lg:col-span-1 space-y-4">
          <OrderBook symbol={activeSymbol} currentPrice={currentTick.bid} />
          <SpreadMonitor symbol={activeSymbol} spread={currentTick.spread || 0.30} />
        </div>
      </div>
    </div>
  );
};

export default MarketPage;
