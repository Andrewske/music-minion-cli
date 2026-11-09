import { describe, expect, it } from 'vitest';
import { formatDuration, formatTimeAgo, largeArtwork } from './storiesFormat';

const NOW = Date.parse('2026-11-08T20:00:00Z');

describe('formatTimeAgo', () => {
  it.each([
    ['2026-11-08T19:59:30Z', 'just now'],
    ['2026-11-08T19:59:00Z', '1 minute ago'],
    ['2026-11-08T02:00:00Z', '18 hours ago'],
    ['2026-11-06T20:00:00Z', '2 days ago'],
    ['not a date', ''],
  ])('%s -> %s', (iso, expected) => {
    expect(formatTimeAgo(iso, NOW)).toBe(expected);
  });
});

describe('formatDuration', () => {
  it('renders m:ss', () => {
    expect(formatDuration(245_000)).toBe('4:05');
  });
});

describe('largeArtwork', () => {
  it('swaps SoundCloud -large artwork for 500px', () => {
    expect(largeArtwork('https://i1.sndcdn.com/artworks-abc-large.jpg')).toBe('https://i1.sndcdn.com/artworks-abc-t500x500.jpg');
    expect(largeArtwork('https://example.com/a.png')).toBe('https://example.com/a.png');
    expect(largeArtwork(null)).toBeNull();
  });
});
