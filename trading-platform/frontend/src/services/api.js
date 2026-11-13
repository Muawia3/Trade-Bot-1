import axios from 'axios';
import { API_BASE_URL } from '../utils/constants';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Interceptor for logging & handling errors
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const errorMsg = error.response?.data?.detail || error.message || 'API Request Failed';
    console.warn(`[API Error] ${error.config?.url || 'request'}:`, errorMsg);
    return Promise.reject(new Error(errorMsg));
  }
);

/* ==========================================================================
   Account API (Matched to /api/v1/account/...)
   ========================================================================== */
export const accountApi = {
  getAccountInfo: () => api.get('/account/overview'),
  getBalance: () => api.get('/account'),
  getStatus: () => api.get('/account')
};

/* ==========================================================================
   Market Data API (Matched to /api/v1/market-data/...)
   ========================================================================== */
export const marketApi = {
  getPrices: (symbol = 'XAUUSD') => 
    api.get(`/market-data/prices/${symbol}`),
  getCandles: (symbol, timeframe = 'M15', count = 100) => 
    api.get('/market-data/candles', { params: { symbol, timeframe, limit: count } }),
  getSymbolInfo: (symbol) => 
    api.get(`/market-data/symbols/${symbol}/info`),
  getAllSymbols: () => 
    api.get('/market-data/symbols')
};

/* ==========================================================================
   Trading API (Matched to /api/v1/trades/...)
   ========================================================================== */
export const tradingApi = {
  getOpenPositions: () => api.get('/trades/open'),
  getTradeHistory: (params = {}) => api.get('/trades', { params }),
  openPosition: (orderData) => api.post('/trades', orderData),
  closePosition: (tradeId, exitPrice = null) => 
    api.post(`/trades/${tradeId}/close`, exitPrice ? { exit_price: exitPrice } : {}),
  modifyPosition: (tradeId, data) => api.patch(`/trades/${tradeId}`, data),
  getPendingOrders: () => api.get('/trades/open')
};

/* ==========================================================================
   Signal API (Matched to /api/v1/signals/...)
   ========================================================================== */
export const signalApi = {
  getActiveSignals: () => api.get('/signals/active'),
  getSignalHistory: (params = {}) => api.get('/signals', { params }),
  getSignalById: (id) => api.get(`/signals/${id}`)
};

/* ==========================================================================
   Strategy API (Matched to /api/v1/strategies/...)
   ========================================================================== */
export const strategyApi = {
  getStrategies: () => api.get('/strategies'),
  getStrategy: (name) => api.get(`/strategies/${name}`),
  updateStrategy: (name, params) => api.patch(`/strategies/${name}`, params),
  toggleStrategy: (name, enabled) => api.post(`/strategies/${name}/toggle`, { enabled })
};

/* ==========================================================================
   Backtest API (Matched to /api/v1/backtests/...)
   ========================================================================== */
export const backtestApi = {
  runBacktest: (config) => api.post('/backtests/run', config),
  getResults: (backtestId) => api.get(`/backtests/${backtestId}`),
  getAllBacktests: (params = {}) => api.get('/backtests', { params })
};

/* ==========================================================================
   Paper Trading API (Matched to /api/v1/paper-trading/...)
   ========================================================================== */
export const paperApi = {
  getPaperAccount: () => api.get('/paper-trading/status'),
  getPaperPositions: () => api.get('/paper-trading/positions'),
  resetPaperAccount: (initialBalance = 10000) => 
    api.post('/paper-trading/reset', { initial_balance: initialBalance })
};

/* ==========================================================================
   Settings API (Matched to /api/v1/settings/...)
   ========================================================================== */
export const settingsApi = {
  getSettings: () => api.get('/settings'),
  updateSettings: (newSettings) => api.put('/settings', newSettings),
  getMt5Status: () => api.get('/settings/mt5-status'),
  reconnectMt5: () => api.post('/settings/mt5-reconnect'),
  switchMode: (mode, confirmLive = false) => 
    api.post('/settings/trading-mode', { mode, confirm_live: confirmLive })
};

/* ==========================================================================
   Analytics API (Matched to /api/v1/trades/...)
   ========================================================================== */
export const analyticsApi = {
  getPerformance: (timeframe = '30d') => 
    api.get('/trades/performance', { params: { timeframe } }).catch(() => null),
  getDailyPnl: (days = 30) => 
    api.get('/trades/daily-pnl', { params: { days } }).catch(() => null),
  getEquityCurve: (range = 'all') => 
    api.get('/trades/equity-curve', { params: { range } }).catch(() => null),
  getTradeDistribution: () => 
    api.get('/trades/distribution').catch(() => null)
};

export default api;
