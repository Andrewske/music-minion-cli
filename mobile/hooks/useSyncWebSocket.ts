/**
 * WebSocket sync hook — connects to backend /ws/sync endpoint.
 * Handles playback state, device list, and comparison sync.
 * Reconnects with exponential backoff, AppState-aware.
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import { usePlayerStore } from '../stores/playerStore';

const MIN_BACKOFF = 1000;
const MAX_BACKOFF = 30000;

interface UseSyncWebSocketOptions {
  serverUrl: string | null;
}

export const useSyncWebSocket = ({ serverUrl }: UseSyncWebSocketOptions) => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(MIN_BACKOFF);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const { type, data } = JSON.parse(event.data);

      switch (type) {
        case 'sync:full':
          if (data.playback) {
            usePlayerStore.getState().syncState(data.playback);
          }
          if (data.devices) {
            usePlayerStore.getState().syncDevices(data.devices);
          }
          break;

        case 'playback:state':
          usePlayerStore.getState().syncState(data);
          break;

        case 'devices:updated':
          usePlayerStore.getState().syncDevices(data);
          break;

        case 'track:emojis_updated': {
          const { track_id, emojis } = data as { track_id: number; emojis: string[] };
          const { currentTrack, queue, set } = usePlayerStore.getState();

          let updatedCurrentTrack = currentTrack;
          if (currentTrack && currentTrack.id === track_id) {
            updatedCurrentTrack = { ...currentTrack, emojis };
          }

          const updatedQueue = queue.map((t) =>
            t.id === track_id ? { ...t, emojis } : t
          );

          if (updatedCurrentTrack !== currentTrack || updatedQueue !== queue) {
            set({ currentTrack: updatedCurrentTrack, queue: updatedQueue });
          }
          break;
        }

        case 'ping':
          break;

        default:
          break;
      }
    } catch {
      // Ignore malformed messages
    }
  }, []);

  const connect = useCallback(() => {
    if (!serverUrl) return;
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    // Derive WS URL from API URL
    const wsUrl = serverUrl
      .replace(/^http/, 'ws')
      .replace(/\/api$/, '/ws/sync');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        backoffRef.current = MIN_BACKOFF;

        // Register device
        const { thisDeviceId, thisDeviceName } = usePlayerStore.getState();
        ws.send(JSON.stringify({
          type: 'device:register',
          id: thisDeviceId,
          name: thisDeviceName,
        }));
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = () => {
        // Will trigger onclose
      };
    } catch {
      scheduleReconnect();
    }
  }, [serverUrl, handleMessage]);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return;
    const delay = backoffRef.current;
    backoffRef.current = Math.min(delay * 2, MAX_BACKOFF);
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, delay);
  }, [connect]);

  // Reconnect when app returns to foreground
  useEffect(() => {
    const handleAppState = (nextState: AppStateStatus) => {
      if (nextState === 'active' && !wsRef.current) {
        backoffRef.current = MIN_BACKOFF;
        connect();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppState);
    return () => subscription.remove();
  }, [connect]);

  // Initial connection
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // Re-register when device name changes
  useEffect(() => {
    let prevName = usePlayerStore.getState().thisDeviceName;
    return usePlayerStore.subscribe((state) => {
      if (state.thisDeviceName !== prevName) {
        prevName = state.thisDeviceName;
        const ws = wsRef.current;
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'device:register',
            id: state.thisDeviceId,
            name: state.thisDeviceName,
          }));
        }
      }
    });
  }, []);

  return { isConnected };
};
