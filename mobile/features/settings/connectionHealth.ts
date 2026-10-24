/**
 * Settings status card: WebSocket status + a timed GET /health → one verdict.
 */
import type { ConnectionStatus } from '../../hooks/useSyncWebSocket';
import { CONNECTION_DOT_COLORS } from '../nav/connectionDot';

export type LatencyReading =
  | { kind: 'pending' }
  | { kind: 'ok'; ms: number }
  | { kind: 'failed'; reason: string };

export type HealthLevel = 'good' | 'degraded' | 'down';

export interface ConnectionHealth {
  level: HealthLevel;
  color: string;
  label: string;
}

/** Round trips slower than this read as "Slow". */
export const SLOW_LATENCY_MS = 800;

const COLORS: Record<HealthLevel, string> = {
  good: CONNECTION_DOT_COLORS.connected,
  degraded: CONNECTION_DOT_COLORS.connecting,
  down: CONNECTION_DOT_COLORS.offline,
};

const health = (level: HealthLevel, label: string): ConnectionHealth => ({ level, color: COLORS[level], label });

export const connectionHealth = (ws: ConnectionStatus, reading: LatencyReading): ConnectionHealth => {
  if (reading.kind === 'failed') return health('down', "Can't reach server");
  if (reading.kind === 'pending') return health('degraded', 'Checking');
  if (ws === 'offline') return health('degraded', 'Live updates offline');
  if (ws === 'connecting') return health('degraded', 'Live updates reconnecting');
  if (reading.ms > SLOW_LATENCY_MS) return health('degraded', 'Slow connection');
  return health('good', 'Connected');
};

/** "84 ms" / "1.2 s"; a dash while pending or after a failure. */
export const formatLatency = (reading: LatencyReading): string => {
  if (reading.kind !== 'ok') return '--';
  const ms = Math.max(0, Math.round(reading.ms));
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
};

/** The backend's /health sits beside /api, not under it. */
export const healthUrl = (serverUrl: string): string =>
  serverUrl.trim().replace(/\/+$/, '').replace(/\/api$/, '') + '/health';

/** "https://pi.tail.ts.net:8446/api" → "pi.tail.ts.net:8446". */
export const serverHost = (serverUrl: string): string =>
  serverUrl.trim().replace(/^[a-z]+:\/\//i, '').replace(/\/+$/, '').replace(/\/api$/, '');
