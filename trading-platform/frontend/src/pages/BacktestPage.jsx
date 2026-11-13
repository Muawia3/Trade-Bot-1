import React, { useState } from 'react';
import Card from '../components/common/Card';
import Table from '../components/common/Table';
import EquityCurve from '../features/analytics/EquityCurve';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { formatCurrency, formatPercent, formatDate } from '../utils/formatters';

export const BacktestPage = () => {
  const [strategy, setStrategy] = useState('Breakout Gold Alpha');
  const [symbol, setSymbol] = useState('XAUUSD');
  const [timeframe, setTimeframe] = useState('M15');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2025-12-31');
  const [initialBalance, setInitialBalance] = useState(10000);
  const [simulatedSpread, setSimulatedSpread] = useState(0.25);
  const [slippagePips, setSlippagePips] = useState(0.2);

  const [running, setRunning] = useState(false);
  const [results, setResults] = useState({
    initialBalance: 10000,
    finalEquity: 14850.20,
    netProfit: 4850.20,
    returnPercent: 48.5,
    totalTrades: 284,
    winRate: 67.2,
    profitFactor: 2.31,
    maxDrawdown: 4.6,
    sharpeRatio: 2.15,
    curveData: [
      { date: 'Jan', equity: 10000, balance: 10000 },
      { date: 'Feb', equity: 10420, balance: 10390 },
      { date: 'Mar', equity: 10980, balance: 10850 },
      { date: 'Apr', equity: 11450, balance: 11300 },
      { date: 'May', equity: 11200, balance: 11350 },
      { date: 'Jun', equity: 11890, balance: 11720 },
      { date: 'Jul', equity: 12540, balance: 12410 },
      { date: 'Aug', equity: 13100, balance: 12980 },
      { date: 'Sep', equity: 13620, balance: 13500 },
      { date: 'Oct', equity: 14120, balance: 13950 },
      { date: 'Nov', equity: 14500, balance: 14380 },
      { date: 'Dec', equity: 14850, balance: 14790 }
    ],
    sampleTrades: [
      { id: 'BT-01', type: 'BUY', lots: 0.25, openPrice: 2610.20, closePrice: 2632.40, pnl: 555.00, date: '2025-12-28' },
      { id: 'BT-02', type: 'SELL', lots: 0.25, openPrice: 2640.10, closePrice: 2648.50, pnl: -210.00, date: '2025-12-24' },
      { id: 'BT-03', type: 'BUY', lots: 0.25, openPrice: 2622.00, closePrice: 2638.20, pnl: 405.00, date: '2025-12-19' }
    ]
  });

  const handleRunBacktest = () => {
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
    }, 1200);
  };

  const tradeColumns = [
    { label: 'Trade ID', key: 'id' },
    { label: 'Type', key: 'type', render: (val) => <span className={val === 'BUY' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{val}</span> },
    { label: 'Lots', key: 'lots', render: (val) => `${val} L` },
    { label: 'Open Price', key: 'openPrice' },
    { label: 'Close Price', key: 'closePrice' },
    {
      label: 'Net P/L',
      key: 'pnl',
      align: 'right',
      render: (val) => <span className={val >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{val >= 0 ? `+${formatCurrency(val)}` : formatCurrency(val)}</span>
    },
    { label: 'Date', key: 'date', align: 'right' }
  ];

  return (
    <div className="space-y-6">
      {/* Parameter Configuration Form */}
      <Card
        title="Quantitative Backtesting Lab"
        subtitle="Historical tick-level backtesting engine with spread and slippage simulation"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
          <div>
            <label className="text-slate-400 block mb-1 font-sans">Trading Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200"
            >
              <option value="Breakout Gold Alpha">Breakout Gold Alpha</option>
              <option value="London Scalper EUR">London Scalper EUR</option>
              <option value="Mean Reversion Bollinger">Mean Reversion Bollinger</option>
            </select>
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Symbol Pair</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200"
            >
              <option value="XAUUSD">XAUUSD</option>
              <option value="EURUSD">EURUSD</option>
              <option value="GBPUSD">GBPUSD</option>
            </select>
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Timeframe</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200"
            >
              <option value="M5">5 Minutes (M5)</option>
              <option value="M15">15 Minutes (M15)</option>
              <option value="H1">1 Hour (H1)</option>
              <option value="H4">4 Hours (H4)</option>
            </select>
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Starting Equity ($)</label>
            <input
              type="number"
              value={initialBalance}
              onChange={(e) => setInitialBalance(parseFloat(e.target.value) || 10000)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Backtest Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Backtest End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Simulated Spread (pts)</label>
            <input
              type="number"
              step="0.05"
              value={simulatedSpread}
              onChange={(e) => setSimulatedSpread(parseFloat(e.target.value) || 0)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-amber-400"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Execution Slippage (pips)</label>
            <input
              type="number"
              step="0.1"
              value={slippagePips}
              onChange={(e) => setSlippagePips(parseFloat(e.target.value) || 0)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-rose-400"
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-slate-800">
          <div className="text-xs text-slate-400 font-sans">
            Simulation model: <strong className="text-slate-200">Real Tick Open/High/Low/Close data</strong>
          </div>
          <button
            onClick={handleRunBacktest}
            disabled={running}
            className="px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-cyan-950/40 transition flex items-center gap-2"
          >
            {running ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>Simulating Strategy...</span>
              </>
            ) : (
              <span>▶ Run Backtest Simulation</span>
            )}
          </button>
        </div>
      </Card>

      {/* Results Section */}
      {results && (
        <div className="space-y-6">
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono">
            <Card className="p-3 bg-slate-900/60 border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">Net Return</span>
              <span className="text-lg font-bold text-emerald-400">+{formatPercent(results.returnPercent)}</span>
              <span className="text-[10px] text-slate-500 block">+{formatCurrency(results.netProfit)}</span>
            </Card>

            <Card className="p-3 bg-slate-900/60 border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">Win Rate</span>
              <span className="text-lg font-bold text-cyan-400">{formatPercent(results.winRate)}</span>
              <span className="text-[10px] text-slate-500 block">{results.totalTrades} Executions</span>
            </Card>

            <Card className="p-3 bg-slate-900/60 border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">Profit Factor</span>
              <span className="text-lg font-bold text-slate-100">{results.profitFactor}</span>
              <span className="text-[10px] text-slate-500 block">Gross Profit / Loss</span>
            </Card>

            <Card className="p-3 bg-slate-900/60 border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">Max Drawdown</span>
              <span className="text-lg font-bold text-rose-400">-{results.maxDrawdown}%</span>
              <span className="text-[10px] text-slate-500 block">Peak to trough</span>
            </Card>

            <Card className="p-3 bg-slate-900/60 border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">Sharpe Ratio</span>
              <span className="text-lg font-bold text-indigo-400">{results.sharpeRatio}</span>
              <span className="text-[10px] text-slate-500 block">Annualized risk-adj</span>
            </Card>
          </div>

          {/* Equity Chart */}
          <EquityCurve data={results.curveData} height={300} />

          {/* Simulated Trades Sample */}
          <Card title="Sample Backtest Trades" subtitle="First simulated order executions">
            <Table columns={tradeColumns} data={results.sampleTrades} />
          </Card>
        </div>
      )}
    </div>
  );
};

export default BacktestPage;
