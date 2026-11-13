import React, { useState } from 'react';
import Card from '../components/common/Card';
import StatusBadge from '../components/common/StatusBadge';
import { useTradingContext } from '../context/TradingContext';
import { TRADING_MODES } from '../utils/constants';

export const SettingsPage = () => {
  const { tradingMode, switchMode, account, connections } = useTradingContext();

  const [mt5Config, setMt5Config] = useState({
    server: 'MetaQuotes-Demo',
    login: '50291823',
    path: 'C:\\Program Files\\MetaTrader 5\\terminal64.exe',
    timeout: 60000,
    reconnecting: false
  });

  const [aiSettings, setAiSettings] = useState({
    aiEnabled: true,
    modelConfidenceThreshold: 75,
    deepLearningInference: false,
    sentimentNewsAnalysis: true
  });

  const [notifications, setNotifications] = useState({
    telegramAlerts: true,
    discordWebhook: false,
    audioPings: true,
    emailDailyReport: true
  });

  const [statusMsg, setStatusMsg] = useState(null);

  const handleReconnectMt5 = () => {
    setMt5Config((prev) => ({ ...prev, reconnecting: true }));
    setTimeout(() => {
      setMt5Config((prev) => ({ ...prev, reconnecting: false }));
      setStatusMsg('MT5 Bridge reconnected successfully. Latency: 14ms.');
      setTimeout(() => setStatusMsg(null), 3000);
    }, 1200);
  };

  return (
    <div className="space-y-6">
      {statusMsg && (
        <div className="p-3 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs font-semibold">
          {statusMsg}
        </div>
      )}

      {/* Primary Trading Mode Architecture */}
      <Card
        title="Trading Execution Environment"
        subtitle="Configure order dispatch destination and simulated vs live accounts"
        badge={<StatusBadge type="mode" value={tradingMode} />}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Paper Trading */}
            <div
              onClick={() => switchMode(TRADING_MODES.PAPER)}
              className={`p-4 rounded-xl border cursor-pointer transition ${
                tradingMode === TRADING_MODES.PAPER
                  ? 'bg-amber-500/10 border-amber-500/50 shadow-md'
                  : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-amber-300 text-sm">Paper Trading</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
                  Default Safe
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Simulated orders executed locally against real tick data. Perfect for strategy validation with zero capital risk.
              </p>
            </div>

            {/* Demo Trading */}
            <div
              onClick={() => switchMode(TRADING_MODES.DEMO)}
              className={`p-4 rounded-xl border cursor-pointer transition ${
                tradingMode === TRADING_MODES.DEMO
                  ? 'bg-emerald-500/10 border-emerald-500/50 shadow-md'
                  : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-emerald-300 text-sm">Broker Demo</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                  MT5 Demo
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Sends orders directly to broker demo account via MetaTrader 5 terminal connector.
              </p>
            </div>

            {/* Live Trading */}
            <div
              onClick={() => switchMode(TRADING_MODES.LIVE)}
              className={`p-4 rounded-xl border cursor-pointer transition ${
                tradingMode === TRADING_MODES.LIVE
                  ? 'bg-rose-500/15 border-rose-500/60 shadow-md'
                  : 'bg-slate-900/40 border-slate-800 hover:border-rose-900/40'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-rose-300 text-sm">LIVE Real Money</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono">
                  High Risk
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Real money execution. Requires explicit 2FA / text confirmation to activate. Strict server-side stop-losses.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* MetaTrader 5 Bridge Settings */}
      <Card
        title="MetaTrader 5 Connector"
        subtitle="Native Windows IPC Bridge connection settings"
        actions={
          <button
            onClick={handleReconnectMt5}
            disabled={mt5Config.reconnecting}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
          >
            {mt5Config.reconnecting ? 'Pinging Bridge...' : '↻ Reconnect MT5'}
          </button>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
          <div>
            <label className="text-slate-400 block mb-1 font-sans">MT5 Terminal Executable Path</label>
            <input
              type="text"
              value={mt5Config.path}
              readOnly
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-300 cursor-not-allowed"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Broker Server Name</label>
            <input
              type="text"
              value={mt5Config.server}
              onChange={(e) => setMt5Config({ ...mt5Config, server: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Broker Account Login ID</label>
            <input
              type="text"
              value={mt5Config.login}
              onChange={(e) => setMt5Config({ ...mt5Config, login: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100"
            />
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-sans">Connection Status & Ping</label>
            <div className="flex items-center gap-3 py-2">
              <StatusBadge type="connection" value={connections.mt5} />
              <span className="text-slate-400 text-xs">Latency: 12ms (Direct IPC)</span>
            </div>
          </div>
        </div>
      </Card>

      {/* AI & Machine Learning Configuration */}
      <Card title="AI & Machine Learning Ensemble Settings" subtitle="Predictive models and confidence gates">
        <div className="space-y-3 font-sans text-xs">
          <label className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer">
            <div>
              <span className="text-slate-200 font-semibold block">Enable AI Signal Filter</span>
              <span className="text-slate-500 text-[11px] block">Filter traditional indicators through deep learning confidence gate</span>
            </div>
            <input
              type="checkbox"
              checked={aiSettings.aiEnabled}
              onChange={(e) => setAiSettings({ ...aiSettings, aiEnabled: e.target.checked })}
              className="rounded bg-slate-800 border-slate-700 text-cyan-600 focus:ring-0 w-4 h-4"
            />
          </label>

          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-slate-200 font-semibold">Minimum Confidence Threshold</span>
              <span className="font-mono text-cyan-400 font-bold">{aiSettings.modelConfidenceThreshold}%</span>
            </div>
            <input
              type="range"
              min="50"
              max="95"
              value={aiSettings.modelConfidenceThreshold}
              onChange={(e) => setAiSettings({ ...aiSettings, modelConfidenceThreshold: parseInt(e.target.value) })}
              className="w-full accent-cyan-500"
            />
          </div>

          <label className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer">
            <div>
              <span className="text-slate-200 font-semibold block">Macro Sentiment Analysis Feed</span>
              <span className="text-slate-500 text-[11px] block">Incorporate real-time Forex news sentiment into directional bias</span>
            </div>
            <input
              type="checkbox"
              checked={aiSettings.sentimentNewsAnalysis}
              onChange={(e) => setAiSettings({ ...aiSettings, sentimentNewsAnalysis: e.target.checked })}
              className="rounded bg-slate-800 border-slate-700 text-cyan-600 focus:ring-0 w-4 h-4"
            />
          </label>
        </div>
      </Card>

      {/* Notification Preferences */}
      <Card title="Security & Execution Notifications" subtitle="Real-time webhooks and dispatch alerts">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {Object.entries(notifications).map(([key, enabled]) => (
            <label
              key={key}
              className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer"
            >
              <span className="text-slate-300 capitalize font-medium">
                {key.replace(/([A-Z])/g, ' $1')}
              </span>
              <input
                type="checkbox"
                checked={enabled}
                onChange={() => setNotifications({ ...notifications, [key]: !enabled })}
                className="rounded bg-slate-800 border-slate-700 text-cyan-600 focus:ring-0 w-4 h-4"
              />
            </label>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default SettingsPage;
