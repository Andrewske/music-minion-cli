import { describe, expect, it } from 'vitest';
import { parseTrackDate } from './trackDate';

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
