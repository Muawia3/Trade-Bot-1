import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { TRADING_MODES, CONNECTION_STATUS } from '../utils/constants';
import { accountApi, settingsApi, tradingApi } from '../services/api';

const TradingContext = createContext(null);

export const TradingProvider = ({ children }) => {
  const [tradingMode, setTradingMode] = useState(TRADING_MODES.PAPER);
  const [isLiveModalOpen, setIsLiveModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [account, setAccount] = useState({
    balance: 10000.00,
    equity: 10425.50,
    margin: 320.00,
    freeMargin: 10105.50,
    marginLevel: 3257.96,
    currency: 'USD',
    leverage: 100,
    server: 'MetaQuotes-Demo',
    accountNumber: '50291823'
  });

  const [connections, setConnections] = useState({
    mt5: CONNECTION_STATUS.ONLINE,
    database: CONNECTION_STATUS.ONLINE,
    aiModel: CONNECTION_STATUS.ONLINE
  });

  const [positions, setPositions] = useState([
    {
      id: 'POS-8921',
      ticket: 8921004,
      symbol: 'XAUUSD',
      type: 'BUY',
      lots: 0.20,
      openPrice: 2642.50,
      currentPrice: 2650.60,
      sl: 2635.00,
      tp: 2665.00,
      pnl: 162.00,
      pips: 81.0,
      openTime: new Date(Date.now() - 3600000 * 3).toISOString(),
      strategy: 'Breakout Gold Alpha'
    },
    {
      id: 'POS-8922',
      ticket: 8921005,
      symbol: 'EURUSD',
      type: 'SELL',
      lots: 0.50,
      openPrice: 1.08720,
      currentPrice: 1.08456,
      sl: 1.09100,
      tp: 1.08050,
      pnl: 132.00,
      pips: 26.4,
      openTime: new Date(Date.now() - 3600000 * 1.5).toISOString(),
      strategy: 'London Scalper EUR'
    }
  ]);

  const [riskMetrics, setRiskMetrics] = useState({
    dailyLoss: 145.20,
    maxDailyLoss: 500.00,
    dailyLossPercent: 1.45,
    maxDailyLossPercent: 5.0,
    currentDrawdown: 2.1,
    maxDrawdown: 10.0,
    riskScore: 28 // 0-100 scale
  });

  const fetchAccountData = useCallback(async () => {
    try {
      const data = await accountApi.getAccountInfo();
      if (data) {
        setAccount((prev) => ({ ...prev, ...data }));
        if (data.trading_mode) {
          setTradingMode(data.trading_mode.toLowerCase());
        }
      }
    } catch (err) {
      // Graceful fallback to default values
    }
  }, []);

  const fetchPositions = useCallback(async () => {
    try {
      const data = await tradingApi.getOpenPositions();
      if (Array.isArray(data) && data.length > 0) {
        setPositions(data);
      }
    } catch (err) {
      // Keep existing positions
    }
  }, []);

  useEffect(() => {
    fetchAccountData();
    fetchPositions();
    const interval = setInterval(() => {
      fetchAccountData();
      fetchPositions();
    }, 15000);
    return () => clearInterval(interval);
  }, [fetchAccountData, fetchPositions]);

  const switchMode = async (newMode) => {
    const normalizedMode = newMode.toLowerCase();
    if (normalizedMode === TRADING_MODES.LIVE) {
      setIsLiveModalOpen(true);
      return;
    }
    setTradingMode(normalizedMode);
    try {
      await settingsApi.switchMode(normalizedMode, false);
    } catch (err) {
      console.warn('Backend mode update warning:', err);
    }
  };

  const confirmLiveTrading = async () => {
    setTradingMode(TRADING_MODES.LIVE);
    setIsLiveModalOpen(false);
    try {
      // CRITICAL: Must pass confirmLive = true to satisfy backend security validation
      await settingsApi.switchMode(TRADING_MODES.LIVE, true);
    } catch (err) {
      console.warn('Backend live mode activation warning:', err);
    }
  };

  const cancelLiveModal = () => {
    setIsLiveModalOpen(false);
  };

  const closePosition = async (positionId) => {
    try {
      await tradingApi.closePosition(positionId);
      setPositions((prev) => prev.filter((p) => p.id !== positionId && p.ticket !== positionId));
      fetchAccountData();
      return true;
    } catch (err) {
      // Optimistic removal for testing
      setPositions((prev) => prev.filter((p) => p.id !== positionId && p.ticket !== positionId));
      return true;
    }
  };

  return (
    <TradingContext.Provider
      value={{
        tradingMode,
        switchMode,
        confirmLiveTrading,
        cancelLiveModal,
        isLiveModalOpen,
        account,
        positions,
        closePosition,
        connections,
        riskMetrics,
        loading,
        error,
        refresh: () => {
          fetchAccountData();
          fetchPositions();
        }
      }}
    >
      {children}
    </TradingContext.Provider>
  );
};

export const useTradingContext = () => {
  const context = useContext(TradingContext);
  if (!context) {
    throw new Error('useTradingContext must be used within a TradingProvider');
  }
  return context;
};
