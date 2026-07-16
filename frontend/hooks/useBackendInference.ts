import { useState, useEffect, useRef, useCallback } from 'react';
import {
  BackendSocketMessage,
  createWebSocketConnection,
  getHealth,
  sendWebSocketFrame,
  WS_BASE,
} from '@/lib/api';

interface BackendStatus {
  connected: boolean;
  reachable: boolean;
  healthy: boolean;
  m1Ready: boolean;
  m4Ready: boolean;
  device: string;
  error?: string;
}

export function useBackendInference() {
  const [status, setStatus] = useState<BackendStatus>({
    connected: false,
    reachable: false,
    healthy: false,
    m1Ready: false,
    m4Ready: false,
    device: 'cpu',
  });

  const [lastMessage, setLastMessage] = useState<BackendSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);

  // Check backend health
  const checkHealth = useCallback(async () => {
    const health = await getHealth();
    if (health) {
      const isHealthy = health.status === 'healthy';
      setStatus({
        connected: wsRef.current?.readyState === WebSocket.OPEN,
        reachable: true,
        healthy: isHealthy,
        m1Ready: health.m1_ready,
        m4Ready: health.m4_ready,
        device: health.device,
        error: undefined,
      });
      return isHealthy;
    }
    setStatus((prev) => ({
      ...prev,
      connected: false,
      reachable: false,
      healthy: false,
      error: 'Backend unreachable',
    }));
    return false;
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) return;
    shouldReconnectRef.current = true;

    console.log('[DEBUG] Attempting WebSocket connection to:', `${WS_BASE}/ws/live`);

    const ws = createWebSocketConnection(
      (event: BackendSocketMessage) => {
        console.log('[DEBUG] WebSocket message received:', event);
        setLastMessage(event);
        if (event.error) {
          console.error('[ERROR] Backend error:', event.error);
          setStatus((prev) => ({ ...prev, error: event.error }));
        }
      },
      (error: string) => {
        console.error('[ERROR] WebSocket error:', error);
        setStatus((prev) => ({ ...prev, connected: false, error }));
      },
      () => {
        console.log('[DEBUG] WebSocket closed');
        wsRef.current = null;
        setStatus((prev) => ({ ...prev, connected: false }));
        if (shouldReconnectRef.current) {
          console.log('[DEBUG] Attempting reconnect in 3s...');
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 3000);
        }
      },
      () => {
        console.log('[OK] WebSocket connected');
        setStatus((prev) => ({ ...prev, connected: true, error: undefined }));
      }
    );

    if (ws) {
      wsRef.current = ws;
    }
  }, []);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setStatus((prev) => ({ ...prev, connected: false }));
  }, []);

  const sendFrame = useCallback((frameBase64: string) => {
    return sendWebSocketFrame(wsRef.current, frameBase64);
  }, []);

  // Check health on mount
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    status,
    lastMessage,
    connect,
    disconnect,
    sendFrame,
    checkHealth,
  };
}
