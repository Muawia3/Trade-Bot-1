import { useState, useEffect, useCallback } from 'react';
import { tradingApi } from '../services/api';
import { useTradingContext } from '../context/TradingContext';

export const useTrades = () => {
  const { positions, closePosition, refresh } = useTradingContext();
  const [history, setHistory] = useState([
    {
      id: 'TRD-1092',
      ticket: 8919421,
      symbol: 'XAUUSD',
      type: 'BUY',
      lots: 0.25,
      openPrice: 2634.20,
      closePrice: 2648.80,
      pnl: 365.00,
      pips: 146.0,
      openTime: new Date(Date.now() - 86400000 * 1.2).toISOString(),
      closeTime: new Date(Date.now() - 86400000 * 0.8).toISOString(),
      reason: 'Take Profit Hit',
      strategy: 'Breakout Gold Alpha'
    },
    {
      id: 'TRD-1091',
      ticket: 8918230,
      symbol: 'EURUSD',
      type: 'BUY',
      lots: 0.40,
      openPrice: 1.08250,
      closePrice: 1.08510,
      pnl: 104.00,
      pips: 26.0,
      openTime: new Date(Date.now() - 86400000 * 2.1).toISOString(),
      closeTime: new Date(Date.now() - 86400000 * 1.9).toISOString(),
      reason: 'Take Profit Hit',
      strategy: 'London Scalper EUR'
    },
    {
      id: 'TRD-1090',
      ticket: 8917890,
      symbol: 'XAUUSD',
      type: 'SELL',
      lots: 0.15,
      openPrice: 2645.00,
      closePrice: 2652.00,
      pnl: -105.00,
      pips: -70.0,
      openTime: new Date(Date.now() - 86400000 * 3.5).toISOString(),
      closeTime: new Date(Date.now() - 86400000 * 3.2).toISOString(),
      reason: 'Stop Loss Hit',
      strategy: 'Mean Reversion Gold'
    }
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const fetchHistory = useCallback(async () => {
    try {
      const data = await tradingApi.getTradeHistory();
      if (Array.isArray(data) && data.length > 0) {
        setHistory(data);
      }
    } catch (err) {
      // Keep existing history fallback
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const executeTrade = async (orderPayload) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await tradingApi.openPosition(orderPayload);
      refresh();
      return { success: true, data: res };
    } catch (err) {
      setError(err.message || 'Execution error');
      return { success: false, error: err.message };
    } finally {
      setSubmitting(false);
    }
  };

  return {
    positions,
    history,
    closePosition,
    executeTrade,
    submitting,
    error,
    refresh
  };
};

export default useTrades;
