import { useState, useEffect, useRef, useCallback } from 'react';
import { createWebSocketConnection, getHealth, PredictionEvent } from '@/lib/api';

interface BackendStatus {
  connected: boolean;
  healthy: boolean;
  m1Ready: boolean;
  m4Ready: boolean;
  device: string;
  error?: string;
}

export function useBackendInference() {
  const [status, setStatus] = useState<BackendStatus>({
    connected: false,
    healthy: false,
    m1Ready: false,
    m4Ready: false,
    device: 'cpu',
  });

  const [predictions, setPredictions] = useState<PredictionEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Check backend health
  const checkHealth = useCallback(async () => {
    const health = await getHealth();
    if (health) {
      setStatus({
        connected: true,
        healthy: health.status === 'healthy',
        m1Ready: health.m1_ready,
        m4Ready: health.m4_ready,
        device: health.device,
      });
      return true;
    }
    setStatus((prev) => ({
      ...prev,
      connected: false,
      healthy: false,
      error: 'Backend unreachable',
    }));
    return false;
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current) return;

    const ws = createWebSocketConnection(
      (event: PredictionEvent) => {
        setPredictions(event);
      },
      (error: string) => {
        setStatus((prev) => ({ ...prev, connected: false, error }));
      },
      () => {
        setStatus((prev) => ({ ...prev, connected: false }));
        // Attempt reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      }
    );

    if (ws) {
      wsRef.current = ws;
      setStatus((prev) => ({ ...prev, connected: true, error: undefined }));
    }
  }, []);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    setStatus((prev) => ({ ...prev, connected: false }));
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
    predictions,
    connect,
    disconnect,
    checkHealth,
  };
}
