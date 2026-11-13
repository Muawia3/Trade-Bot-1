import React, { useState } from 'react';
import Modal from '../../components/common/Modal';

export const StrategyConfig = ({ strategy, isOpen, onClose, onSave }) => {
  if (!strategy) return null;

  const [params, setParams] = useState(
    strategy.parameters || {
      fastEma: 20,
      slowEma: 50,
      rsiPeriod: 14,
      rsiOverbought: 70,
      rsiOversold: 30,
      riskPerTradePercent: 1.0,
      trailingStopTriggerPips: 30,
      maxOpenTradesPerSymbol: 1
    }
  );

  const handleChange = (key, value) => {
    setParams((prev) => ({
      ...prev,
      [key]: Number(value)
    }));
  };

  const handleSave = () => {
    if (onSave) {
      onSave(strategy.id, params);
    }
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Tune Strategy: ${strategy.name}`}
      footer={
        <>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg shadow transition"
          >
            Apply Parameters
          </button>
        </>
      }
    >
      <div className="space-y-4 text-xs font-mono">
        <p className="text-slate-400 font-sans text-xs">
          Adjust algorithmic indicator thresholds and risk parameters for this specific quantitative model.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-slate-400 block mb-1">Fast EMA Period</label>
            <input
              type="number"
              value={params.fastEma}
              onChange={(e) => handleChange('fastEma', e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100"
            />
          </div>
          <div>
            <label className="text-slate-400 block mb-1">Slow EMA Period</label>
            <input
              type="number"
              value={params.slowEma}
              onChange={(e) => handleChange('slowEma', e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-100"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-slate-400 block mb-1">RSI Oversold Level</label>
            <input
              type="number"
              value={params.rsiOversold}
              onChange={(e) => handleChange('rsiOversold', e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-emerald-400"
            />
          </div>
          <div>
            <label className="text-slate-400 block mb-1">RSI Overbought Level</label>
            <input
              type="number"
              value={params.rsiOverbought}
              onChange={(e) => handleChange('rsiOverbought', e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-rose-400"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-slate-400 block mb-1">Risk Per Trade (%)</label>
            <input
              type="number"
              step="0.1"
              value={params.riskPerTradePercent}
              onChange={(e) => handleChange('riskPerTradePercent', e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-cyan-400"
            />
          </div>
          <div>
            <label className="text-slate-400 block mb-1">Trailing Stop (Pips)</label>
            <input
              type="number"
              value={params.trailingStopTriggerPips}
              onChange={(e) => handleChange('trailingStopTriggerPips', e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-amber-400"
            />
          </div>
        </div>
      </div>
    </Modal>
  );
};

export default StrategyConfig;
