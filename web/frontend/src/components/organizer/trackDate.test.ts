import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { formatRelativeDate, parseTrackDate } from './trackDate';

describe('parseTrackDate', () => {
  it('reads offset-free SQLite timestamps as UTC', () => {
    expect(parseTrackDate('2026-05-07 16:00:02')?.toISOString()).toBe('2026-05-07T16:00:02.000Z');
  });

  it('reads SoundCloud timestamps', () => {
    expect(parseTrackDate('2026/09/13 04:35:14 +0000')?.toISOString()).toBe('2026-09-13T04:35:14.000Z');
  });

  it('keeps an explicit offset', () => {
    expect(parseTrackDate('2026-11-14T05:18:15+00:00')?.toISOString()).toBe('2026-11-14T05:18:15.000Z');
  });

  it('rejects missing or junk input', () => {
    expect(parseTrackDate(undefined)).toBeNull();
    expect(parseTrackDate('not a date')).toBeNull();
  });
});

describe('formatRelativeDate', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-16T12:00:00Z'));
  });
  afterEach(() => vi.useRealTimers());

  it('buckets ages into compact units', () => {
    expect(formatRelativeDate('2026-11-16 06:00:00')).toBe('<1d');
    expect(formatRelativeDate('2026-11-13 12:00:00')).toBe('3d');
    expect(formatRelativeDate('2026/11/02 12:00:00 +0000')).toBe('2w');
    expect(formatRelativeDate('2026-06-01 12:00:00')).toBe('5mo');
    expect(formatRelativeDate('2024-11-01 12:00:00')).toBe('2y');
  });

  it('shows a dash for missing or bad dates', () => {
    expect(formatRelativeDate(undefined)).toBe('-');
    expect(formatRelativeDate('nope')).toBe('-');
  });
});
