import { useEffect, useRef, useState, useCallback } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { useRecordComparison, useArchiveTrack } from './useComparison';

export function useIPCWebSocket() {
  // Mutation hooks are stable references from React Query
  const recordComparison = useRecordComparison();
  const archiveTrack = useArchiveTrack();

  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const connectRef = useRef<() => void>();
  const wasConnectedRef = useRef(false);  // Track if we ever successfully connected
  const reconnectAttemptsRef = useRef(0);  // Track reconnection attempts for backoff
  const maxReconnectAttempts = 10;  // Stop trying after 10 failed attempts

  const handleCommand = useCallback((command: string, args: string[]) => {
    // Read FRESH state when command is received (avoids stale closure)
    const { currentPair, playingTrack, setPlaying } = useComparisonStore.getState();

    console.log('Received IPC command:', command, args);

    switch (command) {
      case 'playpause':
        if (playingTrack) {
          setPlaying(null);  // Pause
        } else if (currentPair) {
          setPlaying(currentPair.track_a);  // Play track A
        } else {
          console.log('Play/pause command received but no active comparison');
        }
        break;

      case 'play1':
        if (!currentPair) {
          console.log('Play1 command received but no active comparison');
          break;
        }
        if (playingTrack?.id === currentPair.track_a.id) {
          setPlaying(null);  // Pause if track A is playing
        } else {
          setPlaying(currentPair.track_a);  // Play track A
        }
        break;

      case 'play2':
        if (!currentPair) {
          console.log('Play2 command received but no active comparison');
          break;
        }
        if (playingTrack?.id === currentPair.track_b.id) {
          setPlaying(null);  // Pause if track B is playing
        } else {
          setPlaying(currentPair.track_b);  // Play track B
        }
        break;

      case 'winner':
        if (currentPair) {
          recordComparison.mutate({
            session_id: currentPair.session_id,
            track_a_id: currentPair.track_a.id,
            track_b_id: currentPair.track_b.id,
            winner_id: currentPair.track_a.id,
            priority_path_prefix: undefined,
          });
        } else {
          console.log('Winner command received but no active comparison');
        }
        break;

      case 'archive':
        if (currentPair) {
          archiveTrack.mutate(currentPair.track_a.id);
        } else {
          console.log('Archive command received but no active comparison');
        }
        break;

      default:
        console.log('Unknown IPC command:', command);
    }
  }, [recordComparison, archiveTrack]);

  const connect = useCallback(() => {
    // Prevent duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return; // Already connected or connecting
    }

    try {
      const ws = new WebSocket('ws://localhost:8765');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Connected to IPC WebSocket');
        setIsConnected(true);
        wasConnectedRef.current = true;  // Mark that we successfully connected
        reconnectAttemptsRef.current = 0;  // Reset reconnection attempts on successful connection
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'command') {
            handleCommand(data.command, data.args || []);
          } else if (data.type === 'shutdown') {
            // Backend is shutting down - pause all playback immediately
            console.log('Backend shutdown detected - pausing and reloading page');
            const { setPlaying } = useComparisonStore.getState();
            setPlaying(null);  // Pause playback

            // Reload page after brief delay to clear all state and stop any lingering audio
            setTimeout(() => {
              window.location.reload();
            }, 100);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        // Only pause playback if we were previously connected
        // This prevents pausing when initial connection fails
        if (wasConnectedRef.current) {
          const { setPlaying } = useComparisonStore.getState();
          setPlaying(null);
        }

        // Exponential backoff reconnection with max attempts
        reconnectAttemptsRef.current += 1;

        if (reconnectAttemptsRef.current > maxReconnectAttempts) {
          return; // Give up silently
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 64s, ...
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current - 1), 60000);

        reconnectTimeoutRef.current = setTimeout(() => {
          connectRef.current?.();
        }, delay);
      };

      ws.onerror = () => {
        // WebSocket connection failed - expected if backend isn't ready yet
        //
        // NOTE: Browser will log "WebSocket connection to 'ws://localhost:8765/' failed"
        // to the console during startup race condition. This CANNOT be suppressed via
        // JavaScript - it's normal browser behavior. The reconnection logic below
        // handles it automatically with exponential backoff.
        //
        // Reconnection logic will handle it automatically
      };
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (_) {
      // WebSocket construction failed - silently ignore
      // This is expected if backend isn't running yet
    }
  }, [handleCommand]);

  // Store connect function in ref to avoid circular dependency
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      // Only close if not already closing/closed
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        // Remove event handlers before closing to prevent reconnection
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.onopen = null;

        wsRef.current.close();
      }
      wsRef.current = null;
    }

    // Reset connection tracking
    wasConnectedRef.current = false;
    reconnectAttemptsRef.current = 0;
  };

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect]);

  return {
    isConnected,
    connect,
    disconnect,
  };
}