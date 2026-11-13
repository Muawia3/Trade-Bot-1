import React, { useState } from 'react';
import Modal from '../../components/common/Modal';
import { formatPrice, formatCurrency } from '../../utils/formatters';

export const PositionManager = ({ position, isOpen, onClose, onSave }) => {
  if (!position) return null;

  const [sl, setSl] = useState(position.sl || '');
  const [tp, setTp] = useState(position.tp || '');
  const [partialLots, setPartialLots] = useState(0.01);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (onSave) {
        await onSave(position.id || position.ticket, {
          sl: sl ? parseFloat(sl) : null,
          tp: tp ? parseFloat(tp) : null,
          partialLots: parseFloat(partialLots)
        });
      }
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Manage Position #${position.ticket || position.id} (${position.symbol})`}
      footer={
        <>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg shadow transition disabled:opacity-50"
          >
            {saving ? 'Updating...' : 'Save Parameters'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs font-mono">
        <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 grid grid-cols-2 gap-2 text-[11px]">
          <div>
            <span className="text-slate-500 block">Type & Volume:</span>
            <span className={position.type === 'BUY' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {position.type} {position.lots} Lots
            </span>
          </div>
          <div>
            <span className="text-slate-500 block">Open Price:</span>
            <span className="text-slate-200 font-bold">{formatPrice(position.openPrice, position.symbol)}</span>
          </div>
          <div>
            <span className="text-slate-500 block">Floating P/L:</span>
            <span className="text-emerald-400 font-bold">+{formatCurrency(position.pnl || 0)}</span>
          </div>
          <div>
            <span className="text-slate-500 block">Strategy:</span>
            <span className="text-slate-300">{position.strategy || 'Manual'}</span>
          </div>
        </div>

        <div>
          <label className="block text-slate-400 font-semibold mb-1">Modify Stop Loss Price</label>
          <input
            type="number"
            step="0.01"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            placeholder="e.g. 2635.00"
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-rose-300 focus:outline-none focus:border-rose-500"
          />
        </div>

        <div>
          <label className="block text-slate-400 font-semibold mb-1">Modify Take Profit Price</label>
          <input
            type="number"
            step="0.01"
            value={tp}
            onChange={(e) => setTp(e.target.value)}
            placeholder="e.g. 2670.00"
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-emerald-300 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="pt-2 border-t border-slate-800">
          <label className="block text-slate-400 font-semibold mb-1">Partial Close (Volume to close now)</label>
          <div className="flex gap-2">
            <input
              type="number"
              step="0.01"
              max={position.lots}
              min="0.01"
              value={partialLots}
              onChange={(e) => setPartialLots(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
            />
            <button
              type="button"
              className="px-3 py-2 bg-amber-600/20 hover:bg-amber-600 text-amber-300 hover:text-white rounded-lg text-xs font-semibold border border-amber-500/30 transition"
            >
              Close Partial
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
};

export default PositionManager;
