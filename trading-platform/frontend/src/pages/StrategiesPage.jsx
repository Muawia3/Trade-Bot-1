import React, { useState } from 'react';
import StrategyCard from '../features/strategies/StrategyCard';
import StrategyConfig from '../features/strategies/StrategyConfig';
import SignalDisplay from '../features/strategies/SignalDisplay';

export const StrategiesPage = () => {
  const [strategies, setStrategies] = useState([
    {
      id: 'strat-1',
      name: 'Breakout Gold Alpha',
      description: 'Volatility expansion and Asian session high/low liquidity breakout strategy tailored for XAUUSD.',
      enabled: true,
      symbols: ['XAUUSD'],
      timeframe: 'M15',
      winRate: 68.5,
      profitFactor: 2.18,
      maxDrawdown: '3.8%',
      parameters: {
        fastEma: 20,
        slowEma: 50,
        rsiPeriod: 14,
        rsiOversold: 30,
        rsiOverbought: 70,
        riskPerTradePercent: 1.0,
        trailingStopTriggerPips: 40
      }
    },
    {
      id: 'strat-2',
      name: 'London Scalper EUR',
      description: 'Order block institutional liquidity sweeps during London/New York session overlap for EURUSD & GBPUSD.',
      enabled: true,
      symbols: ['EURUSD', 'GBPUSD'],
      timeframe: 'M5',
      winRate: 72.1,
      profitFactor: 1.95,
      maxDrawdown: '2.9%',
      parameters: {
        fastEma: 10,
        slowEma: 30,
        rsiPeriod: 9,
        rsiOversold: 25,
        rsiOverbought: 75,
        riskPerTradePercent: 0.8,
        trailingStopTriggerPips: 20
      }
    },
    {
      id: 'strat-3',
      name: 'Mean Reversion Bollinger',
      description: 'Statistical mean reversion trading extreme 2.5 standard deviation Bollinger band touches with RSI divergence.',
      enabled: false,
      symbols: ['XAUUSD', 'USDJPY'],
      timeframe: 'H1',
      winRate: 64.0,
      profitFactor: 1.72,
      maxDrawdown: '5.2%',
      parameters: {
        fastEma: 20,
        slowEma: 100,
        rsiPeriod: 14,
        rsiOversold: 20,
        rsiOverbought: 80,
        riskPerTradePercent: 0.5,
        trailingStopTriggerPips: 50
      }
    },
    {
      id: 'strat-4',
      name: 'AI Multi-Factor Ensemble',
      description: 'Deep neural network combining technical indicators, sentiment feeds, and macro volatility forecasts.',
      enabled: true,
      symbols: ['XAUUSD', 'EURUSD'],
      timeframe: 'H4',
      winRate: 74.8,
      profitFactor: 2.65,
      maxDrawdown: '4.1%',
      parameters: {
        fastEma: 50,
        slowEma: 200,
        rsiPeriod: 14,
        rsiOversold: 35,
        rsiOverbought: 65,
        riskPerTradePercent: 1.2,
        trailingStopTriggerPips: 60
      }
    }
  ]);

  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  const handleToggle = (id, newEnabled) => {
    setStrategies((prev) =>
      prev.map((s) => (s.id === id ? { ...s, enabled: newEnabled } : s))
    );
  };

  const handleConfigure = (strat) => {
    setSelectedStrategy(strat);
    setIsConfigOpen(true);
  };

  const handleSaveParams = (id, newParams) => {
    setStrategies((prev) =>
      prev.map((s) => (s.id === id ? { ...s, parameters: newParams } : s))
    );
  };

  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100">Algorithmic Strategies & AI Models</h2>
          <p className="text-xs text-slate-400">
            Control automated trading models, toggle active instruments, and calibrate quantitative risk limits.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="px-3 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            {strategies.filter((s) => s.enabled).length} Active Running
          </span>
          <span className="px-3 py-1 rounded-lg bg-slate-800 text-slate-400">
            {strategies.length} Deployed
          </span>
        </div>
      </div>

      {/* Grid of Strategy Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {strategies.map((strat) => (
          <StrategyCard
            key={strat.id}
            strategy={strat}
            onToggle={handleToggle}
            onConfigure={handleConfigure}
          />
        ))}
      </div>

      {/* Real-time Signal Confluence Inspector */}
      <SignalDisplay
        signal={{
          symbol: 'XAUUSD',
          type: 'BUY',
          strategy: 'Breakout Gold Alpha',
          strength: 88,
          entry: 2650.50,
          sl: 2638.00,
          tp: 2672.00,
          reason: 'Volume breakout above 4H resistance with AI momentum confirmation (RSI 58, MACD positive cross).'
        }}
      />

      {/* Parameter Configuration Modal */}
      {selectedStrategy && (
        <StrategyConfig
          strategy={selectedStrategy}
          isOpen={isConfigOpen}
          onClose={() => setIsConfigOpen(false)}
          onSave={handleSaveParams}
        />
      )}
    </div>
  );
};

export default StrategiesPage;
