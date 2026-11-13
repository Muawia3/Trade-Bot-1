import { useEffect } from 'react';
import { useWebSocketContext } from '../context/WebSocketContext';

export const useWebSocket = (eventType, handler) => {
  const ws = useWebSocketContext();

  useEffect(() => {
    if (!eventType || typeof handler !== 'function') return;
    const unsubscribe = ws.subscribe(eventType, handler);
    return () => unsubscribe();
  }, [eventType, handler, ws]);

  return ws;
};

export default useWebSocket;
