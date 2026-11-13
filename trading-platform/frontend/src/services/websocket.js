import { WS_BASE_URL, WS_STATUS } from '../utils/constants';

class WebSocketService {
  constructor() {
    this.ws = null;
    this.listeners = new Map();
    this.statusListeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectTimeout = null;
    this.status = WS_STATUS.DISCONNECTED;
    this.pingInterval = null;
    this.activeRooms = new Set([
      'ticks:XAUUSD',
      'ticks:EURUSD',
      'signals',
      'trades',
      'account'
    ]);
  }

  connect(url = WS_BASE_URL) {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this._updateStatus(WS_STATUS.CONNECTING);

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._updateStatus(WS_STATUS.CONNECTED);
        this._startHeartbeat();

        // Subscribe to default backend rooms according to websocket_routes.py protocol
        this.activeRooms.forEach((room) => {
          this.subscribeRoom(room);
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Map backend event formats to frontend channels
          if (data.type === 'tick' || data.event === 'tick' || data.symbol) {
            this._dispatchEvent('price_update', data.payload || data);
            if (data.symbol) {
              this._dispatchEvent(`tick:${data.symbol}`, data.payload || data);
            }
          } else if (data.type === 'signal' || data.event === 'signal') {
            this._dispatchEvent('signal_generated', data.payload || data);
          } else if (data.type === 'trade' || data.event === 'trade') {
            this._dispatchEvent('trade_executed', data.payload || data);
          } else if (data.room) {
            this._dispatchEvent(data.room, data.payload || data);
          }

          // Generic dispatch
          this._dispatchEvent(data.type || data.event || 'message', data.payload || data);
        } catch (err) {
          console.warn('[WS] Failed to parse message:', event.data);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('[WS] WebSocket error:', err);
        this._updateStatus(WS_STATUS.ERROR);
      };

      this.ws.onclose = () => {
        this._stopHeartbeat();
        this._updateStatus(WS_STATUS.DISCONNECTED);
        this._scheduleReconnect(url);
      };
    } catch (e) {
      console.warn('[WS] Connection attempt failed:', e);
      this._updateStatus(WS_STATUS.DISCONNECTED);
      this._scheduleReconnect(url);
    }
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this._stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._updateStatus(WS_STATUS.DISCONNECTED);
  }

  subscribeRoom(roomName) {
    this.activeRooms.add(roomName);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'subscribe', room: roomName }));
    }
  }

  unsubscribeRoom(roomName) {
    this.activeRooms.delete(roomName);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'unsubscribe', room: roomName }));
    }
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType).add(callback);

    // If subscribing to a room, send subscription action to backend
    if (eventType.includes(':') || eventType === 'signals' || eventType === 'trades') {
      this.subscribeRoom(eventType);
    }

    return () => {
      const callbacks = this.listeners.get(eventType);
      if (callbacks) {
        callbacks.delete(callback);
      }
    };
  }

  onStatusChange(callback) {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  send(action, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...payload }));
      return true;
    }
    return false;
  }

  _dispatchEvent(type, payload) {
    const callbacks = this.listeners.get(type);
    if (callbacks) {
      callbacks.forEach((cb) => {
        try {
          cb(payload);
        } catch (e) {
          console.error(`[WS] Error in listener for ${type}:`, e);
        }
      });
    }

    // Wildcard '*' listener
    const wildcard = this.listeners.get('*');
    if (wildcard) {
      wildcard.forEach((cb) => cb(type, payload));
    }
  }

  _updateStatus(newStatus) {
    this.status = newStatus;
    this.statusListeners.forEach((cb) => cb(newStatus));
  }

  _scheduleReconnect(url) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 15000);
    this.reconnectAttempts++;
    this.reconnectTimeout = setTimeout(() => {
      this.connect(url);
    }, delay);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Backend websocket_routes.py expects action: "ping"
        this.ws.send(JSON.stringify({ action: 'ping' }));
      }
    }, 30000);
  }

  _stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

export const wsService = new WebSocketService();
export default wsService;
