import { useEffect, useRef, useCallback, useState } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { useRadioStore } from '../stores/radioStore';
import { usePlayerStore } from '../stores/playerStore';

const WS_URL = import.meta.env.PROD
  ? `wss://${window.location.host}/ws/sync`
  : 'ws://localhost:8642/ws/sync';

export function useSyncWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 20;

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const { type, data } = JSON.parse(event.data);

      switch (type) {
        case 'sync:full':
          if (data.comparison?.pair && data.comparison?.session_id) {
            useComparisonStore.getState().joinSession(
              data.comparison.session_id,
              data.comparison.pair,
              data.comparison.prefetched
            );
          }
          if (data.radio?.nowPlaying) {
            useRadioStore.getState().setNowPlaying(data.radio.nowPlaying);
          }
          break;

        case 'comparison:advanced':
          useComparisonStore.getState().setNextPairForComparison(
            data.pair,
            data.prefetched,
            data.session_id
          );
          break;

        case 'comparison:track_selected':
          if (data.track) {
            useComparisonStore.getState().setCurrentTrack(data.track);
          }
          useComparisonStore.getState().setIsPlaying(data.isPlaying);
          break;

        case 'radio:now_playing':
          useRadioStore.getState().setNowPlaying(data);
          break;

        case 'playback:state':
          usePlayerStore.getState().syncState(data);
          break;

        case 'devices:updated':
          usePlayerStore.getState().syncDevices(data);
          break;

        case 'ping':
          break;

        default:
          console.log('Unknown sync message type:', type);
      }
    } catch (error) {
      console.error('Failed to parse sync WebSocket message:', error);
    }
  }, []);

  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Connected to sync WebSocket');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;

        // Register device
        const playerState = usePlayerStore.getState();
        ws.send(JSON.stringify({
          type: 'device:register',
          id: playerState.thisDeviceId,
          name: playerState.thisDeviceName,
        }));
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        reconnectAttemptsRef.current += 1;

        if (reconnectAttemptsRef.current > maxReconnectAttempts) {
          console.log('Max reconnect attempts reached, giving up');
          return;
        }

        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptsRef.current - 1),
          60000
        );
        console.log(`Reconnecting in ${delay}ms...`);

        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = () => {};
    } catch {
      // Connection failed, will retry via onclose
    }
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected };
}
