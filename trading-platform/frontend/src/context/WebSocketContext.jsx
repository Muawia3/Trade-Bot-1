import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import wsService from '../services/websocket';
import { WS_STATUS } from '../utils/constants';

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const [status, setStatus] = useState(WS_STATUS.DISCONNECTED);
  const [latestPrices, setLatestPrices] = useState({
    XAUUSD: { bid: 2650.45, ask: 2650.75, spread: 0.30, time: new Date().toISOString(), change24h: 1.15 },
    EURUSD: { bid: 1.08450, ask: 1.08462, spread: 0.00012, time: new Date().toISOString(), change24h: -0.22 },
    GBPUSD: { bid: 1.29850, ask: 1.29868, spread: 0.00018, time: new Date().toISOString(), change24h: 0.45 },
    USDJPY: { bid: 154.210, ask: 154.225, spread: 0.015, time: new Date().toISOString(), change24h: 0.62 }
  });
  const [latestSignal, setLatestSignal] = useState(null);
  const [latestTrade, setLatestTrade] = useState(null);

  useEffect(() => {
    wsService.connect();
    const unsubStatus = wsService.onStatusChange((newStatus) => setStatus(newStatus));

    const unsubPrices = wsService.subscribe('price_update', (data) => {
      if (data && data.symbol) {
        setLatestPrices((prev) => ({
          ...prev,
          [data.symbol]: {
            ...prev[data.symbol],
            ...data
          }
        }));
      }
    });

    const unsubSignal = wsService.subscribe('signal_generated', (data) => {
      setLatestSignal(data);
    });

    const unsubTrade = wsService.subscribe('trade_executed', (data) => {
      setLatestTrade(data);
    });

    return () => {
      unsubStatus();
      unsubPrices();
      unsubSignal();
      unsubTrade();
      wsService.disconnect();
    };
  }, []);

  const subscribeToChannel = useCallback((eventType, callback) => {
    return wsService.subscribe(eventType, callback);
  }, []);

  const sendMessage = useCallback((type, payload) => {
    return wsService.send(type, payload);
  }, []);

  return (
    <WebSocketContext.Provider
      value={{
        status,
        isConnected: status === WS_STATUS.CONNECTED,
        latestPrices,
        latestSignal,
        latestTrade,
        subscribe: subscribeToChannel,
        sendMessage
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocketContext = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
};
