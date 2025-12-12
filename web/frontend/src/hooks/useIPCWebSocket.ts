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
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      const ws = new WebSocket('ws://localhost:8765');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Connected to IPC WebSocket');
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'command') {
            handleCommand(data.command, data.args || []);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('IPC WebSocket disconnected');
        setIsConnected(false);
        wsRef.current = null;

        // Attempt to reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connectRef.current?.();
        }, 5000);
      };

      ws.onerror = (error) => {
        console.error('IPC WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to connect to IPC WebSocket:', error);
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
      wsRef.current.close();
      wsRef.current = null;
    }
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