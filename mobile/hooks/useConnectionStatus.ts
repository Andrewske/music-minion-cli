/**
 * WebSocket connection status, shared from the root layout (which owns the
 * single useSyncWebSocket call) to anything below it: the drawer's Settings
 * dot today, the Settings screen header later.
 *
 * Provide:  <ConnectionStatusContext.Provider value={{ status, retry }}>
 * Consume:  const { status, retry } = useConnectionStatus();
 */
import { createContext, useContext } from 'react';
import type { ConnectionStatus } from './useSyncWebSocket';

export interface ConnectionState {
  status: ConnectionStatus;
  retry: () => void;
}

export const ConnectionStatusContext = createContext<ConnectionState>({
  status: 'connecting',
  retry: () => undefined,
});

export function useConnectionStatus(): ConnectionState {
  return useContext(ConnectionStatusContext);
}
