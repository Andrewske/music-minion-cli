import { describe, expect, it } from 'vitest';
import type { ComparisonPair, Playlist, TrackInfo } from '@music-minion/shared';
import {
  buildComparisonContext,
  formatDuration,
  formatSessionProgress,
  getCardPlayState,
  playbackFraction,
  selectComparablePlaylists,
  shouldAutoPlayNextPair,
} from './comparisonState';

const playlist = (overrides: Partial<Playlist>): Playlist => ({
  id: 1,
  name: 'P',
  type: 'manual',
  track_count: 10,
  library: 'local',
  pin_order: null,
  ...overrides,
});

const track = (id: number): TrackInfo => ({
  id,
  title: `T${id}`,
  rating: 1500,
  comparison_count: 0,
  wins: 0,
  losses: 0,
  has_waveform: false,
});

describe('selectComparablePlaylists', () => {
  it('keeps manual playlists with 2+ tracks and drops smart ones', () => {
    const result = selectComparablePlaylists([
      playlist({ id: 1, name: 'All', type: 'smart', track_count: 6101 }),
      playlist({ id: 2, name: 'Faves' }),
      playlist({ id: 3, name: 'Tiny', track_count: 1 }),
    ]);
    expect(result.map((p) => p.id)).toEqual([2]);
  });

  it('handles undefined data', () => {
    expect(selectComparablePlaylists(undefined)).toEqual([]);
  });
});

describe('formatSessionProgress', () => {
  it('counts votes this session', () => {
    expect(formatSessionProgress(0)).toBe('No votes yet');
    expect(formatSessionProgress(1)).toBe('1 vote this session');
    expect(formatSessionProgress(14)).toBe('14 votes this session');
  });
});

describe('buildComparisonContext', () => {
  it('queues only the current pair without shuffle', () => {
    const pair: ComparisonPair = { track_a: track(7), track_b: track(9) };
    expect(buildComparisonContext(pair)).toEqual({
      type: 'comparison',
      track_ids: [7, 9],
      shuffle: false,
    });
  });
});

describe('getCardPlayState', () => {
  it('is idle when another track is current', () => {
    expect(getCardPlayState(1, 2, true)).toBe('idle');
    expect(getCardPlayState(1, null, false)).toBe('idle');
  });

  it('reflects play/pause for the current track', () => {
    expect(getCardPlayState(1, 1, true)).toBe('playing');
    expect(getCardPlayState(1, 1, false)).toBe('paused');
  });
});

describe('playbackFraction', () => {
  it('clamps to [0, 1] and tolerates unknown duration', () => {
    expect(playbackFraction(30_000, 60)).toBe(0.5);
    expect(playbackFraction(90_000, 60)).toBe(1);
    expect(playbackFraction(-5, 60)).toBe(0);
    expect(playbackFraction(1000, undefined)).toBe(0);
  });
});

describe('formatDuration', () => {
  it('formats m:ss', () => {
    expect(formatDuration(65.4)).toBe('1:05');
    expect(formatDuration(undefined)).toBe('--:--');
  });
});

describe('shouldAutoPlayNextPair', () => {
  const prev: ComparisonPair = { track_a: track(1), track_b: track(2) };
  const next: ComparisonPair = { track_a: track(3), track_b: track(4) };

  it('auto-plays when a track from the old pair is playing', () => {
    expect(shouldAutoPlayNextPair(prev, next, 1, true)).toBe(true);
    expect(shouldAutoPlayNextPair(prev, next, 2, true)).toBe(true);
  });

  it('does nothing when the comparison was not playing', () => {
    expect(shouldAutoPlayNextPair(prev, next, 1, false)).toBe(false);
    expect(shouldAutoPlayNextPair(prev, next, null, true)).toBe(false);
    expect(shouldAutoPlayNextPair(prev, next, 99, true)).toBe(false);
  });

  it('leaves a track alone when it carried over into the new pair', () => {
    const carried: ComparisonPair = { track_a: track(5), track_b: track(1) };
    expect(shouldAutoPlayNextPair(prev, carried, 1, true)).toBe(false);
  });
});
