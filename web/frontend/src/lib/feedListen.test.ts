import { describe, expect, it } from 'vitest';
import {
  INITIAL_LISTEN_STATE,
  MAX_SAMPLE_GAP_MS,
  formatListenTime,
  listenStatsFor,
  recordListenSample,
  type ListenSample,
  type ListenState,
} from './feedListen';

const replay = (samples: ListenSample[]): ListenState =>
  samples.reduce(recordListenSample, INITIAL_LISTEN_STATE);

const at = (at: number, positionMs: number, isPlaying = true, trackId: number | null = 1): ListenSample => ({
  trackId,
  isPlaying,
  positionMs,
  at,
});

describe('feed listen accounting', () => {
  it('counts wall-clock time between playing samples of the same track', () => {
    const state = replay([at(0, 0), at(1_000, 1_000), at(2_000, 2_000)]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 2, maxPositionMs: 2_000 });
  });

  it('records a forward seek as position reached, not time played', () => {
    const state = replay([at(0, 0), at(1_000, 1_000), at(2_000, 90_000)]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 2, maxPositionMs: 90_000 });
  });

  it('ignores paused time and caps long gaps from a sleeping tab', () => {
    const paused = replay([at(0, 0), at(1_000, 1_000), at(2_000, 1_000, false), at(60_000, 1_000, false)]);
    expect(listenStatsFor(paused, 1).listenSeconds).toBe(1);
    const asleep = replay([at(0, 0), at(600_000, 600_000)]);
    expect(listenStatsFor(asleep, 1).listenSeconds).toBe(MAX_SAMPLE_GAP_MS / 1000);
  });

  it('keeps tallies per track across track changes', () => {
    const state = replay([at(0, 0), at(3_000, 3_000), at(4_000, 0, true, 2), at(5_000, 1_000, true, 2)]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 3, maxPositionMs: 3_000 });
    expect(listenStatsFor(state, 2)).toEqual({ listenSeconds: 1, maxPositionMs: 1_000 });
  });

  it('reports zero for tracks that never played', () => {
    expect(listenStatsFor(INITIAL_LISTEN_STATE, 7)).toEqual({ listenSeconds: 0, maxPositionMs: 0 });
    expect(listenStatsFor(INITIAL_LISTEN_STATE, null)).toEqual({ listenSeconds: 0, maxPositionMs: 0 });
  });

  it('formats seconds as m:ss', () => {
    expect(formatListenTime(83.4)).toBe('1:23');
    expect(formatListenTime(null)).toBe('—');
  });
});
