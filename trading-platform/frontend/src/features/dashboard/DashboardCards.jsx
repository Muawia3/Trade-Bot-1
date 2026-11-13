import React from 'react';
import Card from '../../components/common/Card';
import { formatCurrency, formatPercent, getPnlColor, getPnlBg } from '../../utils/formatters';
import { useTradingContext } from '../../context/TradingContext';

export const DashboardCards = () => {
  const { account, positions, riskMetrics } = useTradingContext();

  const totalPnl = positions.reduce((acc, pos) => acc + (pos.pnl || 0), 0);
  const dailyPnl = 285.50; // Mock or calculated daily P/L
  const dailyPnlPercent = 2.85;

  const cards = [
    {
      title: 'Total Balance',
      value: formatCurrency(account.balance),
      subtext: `Currency: ${account.currency}`,
      icon: (
        <span className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </span>
      )
    },
    {
      title: 'Net Equity',
      value: formatCurrency(account.equity),
      subtext: `Free Margin: ${formatCurrency(account.freeMargin)}`,
      icon: (
        <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </span>
      )
    },
    {
      title: 'Today’s Realized P/L',
      value: dailyPnl >= 0 ? `+${formatCurrency(dailyPnl)}` : formatCurrency(dailyPnl),
      subtext: `${formatPercent(dailyPnlPercent)} today`,
      badgeColor: getPnlBg(dailyPnl),
      valueColor: getPnlColor(dailyPnl),
      icon: (
        <span className={`p-2 rounded-lg ${getPnlBg(dailyPnl)}`}>
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </span>
      )
    },
    {
      title: 'Active Exposure',
      value: `${positions.length} Active`,
      subtext: `Open Floating: ${formatCurrency(totalPnl)}`,
      valueColor: getPnlColor(totalPnl),
      icon: (
        <span className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </span>
      )
    }
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, idx) => (
        <Card key={idx} className="hover:border-slate-700/80 transition-all">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{card.title}</p>
              <h4 className={`text-xl lg:text-2xl font-black font-mono mt-1 ${card.valueColor || 'text-slate-100'}`}>
                {card.value}
              </h4>
              <p className="text-[11px] text-slate-400 mt-1 font-mono">{card.subtext}</p>
            </div>
            {card.icon}
          </div>
        </Card>
      ))}
    </div>
  );
};

export default DashboardCards;
