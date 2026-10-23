import { describe, expect, it } from 'vitest';
import { describeListen, formatDuration, formatRelativeTime } from './historyFormat';

const NOW = Date.parse('2026-10-23T22:40:00Z');

describe('formatRelativeTime', () => {
  it('reads UTC timestamps with a Z suffix', () => {
    expect(formatRelativeTime('2026-10-23T22:33:07Z', NOW)).toBe('6m ago');
    expect(formatRelativeTime('2026-10-23T19:40:00Z', NOW)).toBe('3h ago');
    expect(formatRelativeTime('2026-10-21T22:40:00Z', NOW)).toBe('2d ago');
  });

  it('clamps future times to "just now" instead of going negative', () => {
    expect(formatRelativeTime('2026-10-24T05:33:07Z', NOW)).toBe('just now');
  });

  it('shows "just now" under a minute', () => {
    expect(formatRelativeTime('2026-10-23T22:39:30Z', NOW)).toBe('just now');
  });

  it('returns empty for unparseable input', () => {
    expect(formatRelativeTime('', NOW)).toBe('');
    expect(formatRelativeTime('nope', NOW)).toBe('');
  });
});

describe('describeListen', () => {
  it('labels the newest open entry as now playing', () => {
    expect(describeListen({ ended_at: null, duration_ms: 0 }, true)).toBe('Now playing');
  });

  it('labels zero-length rows as skipped', () => {
    expect(describeListen({ ended_at: null, duration_ms: 0 }, false)).toBe('skipped');
    expect(describeListen({ ended_at: '2026-10-23T22:33:07Z', duration_ms: 400 }, true)).toBe(
      'skipped'
    );
  });

  it('formats real listens as m:ss', () => {
    expect(describeListen({ ended_at: '2026-10-23T22:33:07Z', duration_ms: 95_000 }, false)).toBe(
      '1:35'
    );
  });
});

describe('formatDuration', () => {
  it('pads seconds', () => {
    expect(formatDuration(61_000)).toBe('1:01');
  });
});
