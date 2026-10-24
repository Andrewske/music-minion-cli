import { describe, expect, it } from 'vitest';
import { CONNECTION_DOT_COLORS } from '../nav/connectionDot';
import {
  SLOW_LATENCY_MS,
  connectionHealth,
  formatLatency,
  healthUrl,
  serverHost,
} from './connectionHealth';

describe('connectionHealth', () => {
  it('is green when connected and fast', () => {
    const h = connectionHealth('connected', { kind: 'ok', ms: 84 });
    expect(h).toEqual({ level: 'good', color: CONNECTION_DOT_COLORS.connected, label: 'Connected' });
  });

  it('is amber when slow', () => {
    const h = connectionHealth('connected', { kind: 'ok', ms: SLOW_LATENCY_MS + 1 });
    expect(h.level).toBe('degraded');
    expect(h.label).toBe('Slow connection');
  });

  it('is amber when HTTP works but the websocket does not', () => {
    expect(connectionHealth('offline', { kind: 'ok', ms: 50 }).label).toBe('Live updates offline');
    expect(connectionHealth('connecting', { kind: 'ok', ms: 50 }).label).toBe('Live updates reconnecting');
  });

  it('is amber while checking', () => {
    expect(connectionHealth('connected', { kind: 'pending' }).level).toBe('degraded');
  });

  it('is red when the health check fails, whatever the websocket says', () => {
    const h = connectionHealth('connected', { kind: 'failed', reason: 'timeout' });
    expect(h.level).toBe('down');
    expect(h.color).toBe(CONNECTION_DOT_COLORS.offline);
  });
});

describe('formatLatency', () => {
  it('formats ms and seconds', () => {
    expect(formatLatency({ kind: 'ok', ms: 83.6 })).toBe('84 ms');
    expect(formatLatency({ kind: 'ok', ms: 1240 })).toBe('1.2 s');
    expect(formatLatency({ kind: 'ok', ms: -3 })).toBe('0 ms');
  });

  it('shows a dash without a reading', () => {
    expect(formatLatency({ kind: 'pending' })).toBe('--');
    expect(formatLatency({ kind: 'failed', reason: 'x' })).toBe('--');
  });
});

describe('healthUrl', () => {
  it('swaps a trailing /api for /health', () => {
    expect(healthUrl('https://pi:8446/api')).toBe('https://pi:8446/health');
    expect(healthUrl('https://pi:8446/api/ ')).toBe('https://pi:8446/health');
    expect(healthUrl('http://10.0.0.2:8642')).toBe('http://10.0.0.2:8642/health');
  });
});

describe('serverHost', () => {
  it('strips the scheme and /api', () => {
    expect(serverHost('https://pi.tail.ts.net:8446/api')).toBe('pi.tail.ts.net:8446');
    expect(serverHost('http://10.0.0.2:8642/')).toBe('10.0.0.2:8642');
  });
});
