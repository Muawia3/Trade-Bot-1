import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/common/Sidebar';
import Header from '../components/common/Header';
import Modal from '../components/common/Modal';
import ErrorBoundary from '../components/common/ErrorBoundary';
import { useTradingContext } from '../context/TradingContext';

export const MainLayout = () => {
  const { isLiveModalOpen, confirmLiveTrading, cancelLiveModal } = useTradingContext();
  const [confirmText, setConfirmText] = useState('');

  const handleConfirmLive = () => {
    if (confirmText.toUpperCase() === 'CONFIRM LIVE') {
      confirmLiveTrading();
      setConfirmText('');
    }
  };

  return (
    <div className="flex min-h-screen bg-[#080c14] text-slate-100">
      {/* Navigation Sidebar */}
      <Sidebar />

      {/* Main Body */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header />

        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-[1920px] w-full mx-auto">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>

      {/* Safety Warning Modal for LIVE Trading */}
      <Modal
        isOpen={isLiveModalOpen}
        onClose={cancelLiveModal}
        title="⚠️ REAL CAPITAL AT RISK: SWITCH TO LIVE TRADING"
        footer={
          <>
            <button
              onClick={cancelLiveModal}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
            >
              Cancel (Stay Safe)
            </button>
            <button
              onClick={handleConfirmLive}
              disabled={confirmText.toUpperCase() !== 'CONFIRM LIVE'}
              className="px-4 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold rounded-lg shadow-lg shadow-rose-900/50 transition"
            >
              Activate Live Trading
            </button>
          </>
        }
      >
        <div className="space-y-4 text-xs text-slate-300">
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300">
            <strong>Warning:</strong> You are about to enable <strong>LIVE REAL-MONEY TRADING</strong>. Orders will be submitted directly to your connected MetaTrader 5 broker account.
          </div>
          <p>
            Automated algorithmic execution carries substantial financial risk. Ensure you have verified risk limits, maximum drawdown thresholds, and stop losses.
          </p>
          <div className="space-y-2 pt-2">
            <label className="block text-slate-400 font-medium">
              Type <span className="font-mono text-rose-400 font-bold">CONFIRM LIVE</span> to proceed:
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="CONFIRM LIVE"
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono uppercase focus:outline-none focus:border-rose-500"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default MainLayout;
