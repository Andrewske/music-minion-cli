# Frontend Sync Hook

## Files to Modify/Create
- `web/frontend/src/hooks/useSyncWebSocket.ts` (new)
- `web/frontend/src/routes/__root.tsx` (modify)

## Implementation Details

### Part 1: Create useSyncWebSocket Hook

```typescript
// web/frontend/src/hooks/useSyncWebSocket.ts
import { useEffect, useRef, useCallback, useState } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { useRadioStore } from '../stores/radioStore';

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
          if (data.comparison?.pair) {
            useComparisonStore.getState().setCurrentPair(
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
            data.prefetched
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
```

### Part 2: Integrate in Root Layout

```typescript
// web/frontend/src/routes/__root.tsx - ADD import
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';

// Inside the RootComponent function, ADD:
const { isConnected: isSyncConnected } = useSyncWebSocket();

// OPTIONAL: Add connection indicator to UI
// {isSyncConnected ? '🟢' : '🔴'}
```

### Part 3: Reduce/Remove Polling

Find the existing 5-second polling for radio now-playing in `__root.tsx`:

```typescript
// BEFORE: refetchInterval: 5000
// AFTER: refetchInterval: 30000 (fallback only)
// OR: Remove the polling entirely if WebSocket covers it
```

## Acceptance Criteria

1. TypeScript compiles: `cd web/frontend && npm run type-check`
2. Start frontend: `npm run dev`
3. Open browser console - should see "Connected to sync WebSocket"
4. Open two browser tabs
5. Actions in one tab should appear in the other via WebSocket

## Dependencies

- Task 01 (Backend WebSocket Core)
- Task 02 (Backend Broadcast Integration)

## Commits

```bash
git add web/frontend/src/hooks/useSyncWebSocket.ts
git commit -m "feat(sync): add useSyncWebSocket hook for frontend"

git add web/frontend/src/routes/__root.tsx
git commit -m "feat(sync): integrate useSyncWebSocket in root layout"
```
