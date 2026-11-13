import React, { useState } from 'react';
import PositionsTable from '../features/trading/PositionsTable';
import TradeHistory from '../features/trading/TradeHistory';
import QuickTrade from '../features/trading/QuickTrade';
import PositionManager from '../features/trading/PositionManager';
import { useTradingContext } from '../context/TradingContext';

export const TradingPage = () => {
  const { positions } = useTradingContext();
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [isManagerOpen, setIsManagerOpen] = useState(false);

  const handleModifyPosition = (pos) => {
    setSelectedPosition(pos);
    setIsManagerOpen(true);
  };

  const handleSavePosition = async (id, updatedParams) => {
    console.log('Updated position:', id, updatedParams);
    // In real environment, API call will be made
  };

  return (
    <div className="space-y-6">
      {/* Upper Section: Quick Trade Execution & Active Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <QuickTrade defaultSymbol="XAUUSD" />
        </div>
        <div className="lg:col-span-2">
          <PositionsTable onModifyPosition={handleModifyPosition} />
        </div>
      </div>

      {/* Lower Section: Full Trade History */}
      <div>
        <TradeHistory />
      </div>

      {/* Position Manager Modal */}
      {selectedPosition && (
        <PositionManager
          position={selectedPosition}
          isOpen={isManagerOpen}
          onClose={() => setIsManagerOpen(false)}
          onSave={handleSavePosition}
        />
      )}
    </div>
  );
};

export default TradingPage;
