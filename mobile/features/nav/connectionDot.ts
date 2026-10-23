/**
 * Colour + spoken label for the connection dot (drawer Settings row).
 */
import type { ConnectionStatus } from '../../hooks/useSyncWebSocket';

export const CONNECTION_DOT_COLORS: Record<ConnectionStatus, string> = {
  connected: '#4CAF50',
  connecting: '#FFB300',
  offline: '#E53935',
};

const SPOKEN: Record<ConnectionStatus, string> = {
  connected: 'connected',
  connecting: 'reconnecting',
  offline: 'offline',
};

/** Accessibility label for a nav row that carries the connection dot. */
export function connectionLabel(rowLabel: string, status: ConnectionStatus): string {
  return `${rowLabel}, server ${SPOKEN[status]}`;
}
