export const TRADING_MODES = {
  PAPER: 'paper',
  LIVE: 'live',
  DEMO: 'demo'
};

export const SYMBOLS = {
  XAUUSD: 'XAUUSD',
  EURUSD: 'EURUSD',
  GBPUSD: 'GBPUSD',
  USDJPY: 'USDJPY',
  AUDUSD: 'AUDUSD'
};

export const DEFAULT_SYMBOL = 'XAUUSD';

export const TIMEFRAMES = [
  { label: '1m', value: 'M1' },
  { label: '5m', value: 'M5' },
  { label: '15m', value: 'M15' },
  { label: '30m', value: 'M30' },
  { label: '1h', value: 'H1' },
  { label: '4h', value: 'H4' },
  { label: '1D', value: 'D1' }
];

export const ORDER_TYPES = {
  BUY: 'BUY',
  SELL: 'SELL',
  BUY_LIMIT: 'BUY_LIMIT',
  SELL_LIMIT: 'SELL_LIMIT',
  BUY_STOP: 'BUY_STOP',
  SELL_STOP: 'SELL_STOP'
};

export const STRATEGY_TYPES = {
  TREND_FOLLOWING: 'Trend Following',
  MEAN_REVERSION: 'Mean Reversion',
  BREAKOUT: 'Breakout',
  ML_ENSEMBLE: 'AI / Machine Learning Ensemble',
  GRID_HEDGING: 'Dynamic Hedging'
};

export const WS_STATUS = {
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  DISCONNECTED: 'DISCONNECTED',
  ERROR: 'ERROR'
};

export const CONNECTION_STATUS = {
  ONLINE: 'ONLINE',
  OFFLINE: 'OFFLINE',
  SYNCING: 'SYNCING'
};

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
export const WS_BASE_URL =
  import.meta.env.VITE_WS_URL ||
  (typeof window !== 'undefined'
    ? `ws://${window.location.host}/ws/live`
    : 'ws://localhost:8000/ws/live');
