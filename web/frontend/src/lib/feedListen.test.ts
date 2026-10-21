import { describe, expect, it } from 'vitest';
import {
  INITIAL_LISTEN_STATE,
  formatListenTime,
  listenStatsFor,
  playedListenStatsFor,
  recordListenEvent,
  type ListenEvent,
  type ListenState,
} from './feedListen';

const replay = (events: ListenEvent[]): ListenState => events.reduce(recordListenEvent, INITIAL_LISTEN_STATE);

const progress = (positionMs: number, trackId = 1, source = 'A'): ListenEvent => ({
  kind: 'progress',
  source,
  trackId,
  positionMs,
});
const seek = (positionMs: number, trackId = 1, source = 'A'): ListenEvent => ({
  kind: 'seek',
  source,
  trackId,
  positionMs,
});

describe('feed listen accounting', () => {
  it('counts media position advanced between progress events', () => {
    const state = replay([progress(0), progress(250), progress(500), progress(2_000)]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 2, maxPositionMs: 2_000 });
  });

  it('counts nothing while buffering or stalled, since the position never moves', () => {
    const state = replay([progress(1_000), progress(1_000), progress(1_000), progress(1_000)]);
    expect(listenStatsFor(state, 1).listenSeconds).toBe(0);
  });

  it('records a forward seek as position reached, not time played', () => {
    const state = replay([progress(0), progress(1_000), seek(90_000), progress(90_250)]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 1.3, maxPositionMs: 90_250 });
  });

  it('keeps the furthest position across a rapid forward-and-back seek', () => {
    const state = replay([progress(0), progress(1_000), seek(120_000), seek(10_000), progress(10_250)]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 1.3, maxPositionMs: 120_000 });
  });

  it('ignores backward jumps and untrusted large jumps without a seek event', () => {
    const state = replay([progress(0), progress(1_000), progress(500), progress(60_000)]);
    expect(listenStatsFor(state, 1).listenSeconds).toBe(1);
  });

  it('keeps tallies per track and cursors per element', () => {
    const state = replay([
      progress(0, 1, 'A'),
      progress(3_000, 1, 'A'),
      progress(0, 2, 'B'),
      progress(1_000, 2, 'B'),
      progress(3_500, 1, 'A'),
    ]);
    expect(listenStatsFor(state, 1)).toEqual({ listenSeconds: 3.5, maxPositionMs: 3_500 });
    expect(listenStatsFor(state, 2)).toEqual({ listenSeconds: 1, maxPositionMs: 1_000 });
  });

  it('reports zero for tracks that never played, and undefined from the played-only variant', () => {
    expect(listenStatsFor(INITIAL_LISTEN_STATE, 7)).toEqual({ listenSeconds: 0, maxPositionMs: 0 });
    expect(listenStatsFor(INITIAL_LISTEN_STATE, null)).toEqual({ listenSeconds: 0, maxPositionMs: 0 });
    expect(playedListenStatsFor(INITIAL_LISTEN_STATE, 7)).toBeUndefined();
    expect(playedListenStatsFor(replay([progress(0), progress(800)]), 1)).toEqual({
      listenSeconds: 0.8,
      maxPositionMs: 800,
    });
  });

  it('formats seconds as m:ss', () => {
    expect(formatListenTime(83.4)).toBe('1:23');
    expect(formatListenTime(null)).toBe('—');
  });
});
