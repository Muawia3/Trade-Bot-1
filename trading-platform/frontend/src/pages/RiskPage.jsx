import React from 'react';
import RiskGauge from '../features/risk/RiskGauge';
import DailyLossTracker from '../features/risk/DailyLossTracker';
import PositionSizeCalc from '../features/risk/PositionSizeCalc';
import RiskConfig from '../features/risk/RiskConfig';
import Card from '../components/common/Card';
import Table from '../components/common/Table';
import { formatDate } from '../utils/formatters';
import { useTradingContext } from '../context/TradingContext';

export const RiskPage = () => {
  const { riskMetrics } = useTradingContext();

  const riskAlerts = [
    {
      id: 'ALT-401',
      severity: 'WARNING',
      event: 'Spread Spiked Above Threshold',
      details: 'XAUUSD spread reached 0.85 pts during Asian market rollover. New entries paused.',
      timestamp: new Date(Date.now() - 3600000 * 5).toISOString()
    },
    {
      id: 'ALT-400',
      severity: 'INFO',
      event: 'Daily Loss Reset',
      details: 'Daily circuit breaker counter reset to $0.00 at 00:00 UTC server time.',
      timestamp: new Date(Date.now() - 3600000 * 12).toISOString()
    },
    {
      id: 'ALT-399',
      severity: 'CRITICAL',
      event: 'High Impact News Approaching',
      details: 'US CPI Release scheduled in 30 minutes. Auto-trading orders paused by calendar filter.',
      timestamp: new Date(Date.now() - 86400000).toISOString()
    }
  ];

  const alertColumns = [
    {
      label: 'Severity',
      key: 'severity',
      render: (val) => {
        let style = 'bg-blue-500/10 text-blue-400 border-blue-500/30';
        if (val === 'CRITICAL') style = 'bg-rose-500/15 text-rose-400 border-rose-500/30 font-bold';
        if (val === 'WARNING') style = 'bg-amber-500/15 text-amber-300 border-amber-500/30 font-bold';
        return <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${style}`}>{val}</span>;
      }
    },
    {
      label: 'Security Event',
      key: 'event',
      render: (val) => <strong className="text-slate-100">{val}</strong>
    },
    {
      label: 'System Action / Details',
      key: 'details',
      render: (val) => <span className="text-slate-300 font-sans text-xs">{val}</span>
    },
    {
      label: 'Timestamp',
      key: 'timestamp',
      align: 'right',
      render: (val) => formatDate(val, true)
    }
  ];

  return (
    <div className="space-y-6">
      {/* Top row: Exposure Gauge and Circuit Breaker tracker */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RiskGauge score={riskMetrics.riskScore || 28} />
        <DailyLossTracker
          currentLoss={riskMetrics.dailyLoss || 145.20}
          maxDailyLoss={riskMetrics.maxDailyLoss || 500.00}
          currentDrawdown={riskMetrics.currentDrawdown || 2.1}
          maxDrawdown={riskMetrics.maxDrawdown || 10.0}
        />
      </div>

      {/* Middle row: Position Size Calculator and Server Risk Policy Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PositionSizeCalc />
        <RiskConfig onSave={(p) => console.log('Saved risk policy:', p)} />
      </div>

      {/* Audit Log / Risk Alerts History */}
      <Card title="Risk Engine Security Log" subtitle="Real-time log of automated risk interventions and throttles">
        <Table columns={alertColumns} data={riskAlerts} emptyMessage="No active risk warnings." />
      </Card>
    </div>
  );
};

export default RiskPage;
