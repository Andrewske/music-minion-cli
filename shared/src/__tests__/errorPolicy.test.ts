import { describe, it, expect } from 'vitest';
import {
  recordError,
  clearErrorWindow,
  isBreakerTripped,
  decidePlaybackError,
  shouldSuppressPrunedSkip,
  initialErrorWindow,
  ERROR_WINDOW_MS,
  ERROR_THRESHOLD,
  PRUNE_SUPPRESSION_WINDOW_MS,
} from '../playback/errorPolicy.js';
import type { ErrorWindowState } from '../playback/errorPolicy.js';

const T0 = 1_000_000;

const recordN = (n: number, start: number, spacingMs = 100): ErrorWindowState => {
  let state = initialErrorWindow;
  for (let i = 0; i < n; i++) {
    state = recordError(state, start + i * spacingMs);
  }
  return state;
};

describe('recordError', () => {
  it('appends the new error time', () => {
    const state = recordError(initialErrorWindow, T0);
    expect(state.errorTimes).toEqual([T0]);
  });

  it('does not mutate the previous state', () => {
    const before = recordError(initialErrorWindow, T0);
    recordError(before, T0 + 1);
    expect(before.errorTimes).toEqual([T0]);
  });

  it('prunes errors older than the window', () => {
    const old = recordError(initialErrorWindow, T0);
    const state = recordError(old, T0 + ERROR_WINDOW_MS);
    expect(state.errorTimes).toEqual([T0 + ERROR_WINDOW_MS]);
  });

  it('keeps errors still inside the window', () => {
    const old = recordError(initialErrorWindow, T0);
    const state = recordError(old, T0 + ERROR_WINDOW_MS - 1);
    expect(state.errorTimes).toHaveLength(2);
  });
});

describe('isBreakerTripped', () => {
  it('is false below the threshold', () => {
    expect(isBreakerTripped(recordN(ERROR_THRESHOLD - 1, T0))).toBe(false);
  });

  it('trips at the threshold within the window', () => {
    expect(isBreakerTripped(recordN(ERROR_THRESHOLD, T0))).toBe(true);
  });

  it('does not trip when errors are spread beyond the window', () => {
    const state = recordN(ERROR_THRESHOLD, T0, ERROR_WINDOW_MS);
    expect(isBreakerTripped(state)).toBe(false);
  });

  it('resets after clearErrorWindow', () => {
    const tripped = recordN(ERROR_THRESHOLD, T0);
    expect(isBreakerTripped(tripped)).toBe(true);
    expect(isBreakerTripped(clearErrorWindow())).toBe(false);
  });
});

describe('decidePlaybackError', () => {
  it('returns breaker when the threshold is reached, even if a retry is available', () => {
    const state = recordN(ERROR_THRESHOLD, T0);
    expect(decidePlaybackError(state, 42, null)).toBe('breaker');
  });

  it('returns retry for a track that has not been retried this playthrough', () => {
    const state = recordError(initialErrorWindow, T0);
    expect(decidePlaybackError(state, 42, null)).toBe('retry');
  });

  it('returns retry when a different track was the one previously retried', () => {
    const state = recordError(initialErrorWindow, T0);
    expect(decidePlaybackError(state, 42, 7)).toBe('retry');
  });

  it('returns skip when the track already had its retry', () => {
    const state = recordError(initialErrorWindow, T0);
    expect(decidePlaybackError(state, 42, 42)).toBe('skip');
  });

  it('returns skip when the track is not retryable (null)', () => {
    const state = recordError(initialErrorWindow, T0);
    expect(decidePlaybackError(state, null, null)).toBe('skip');
  });
});

describe('shouldSuppressPrunedSkip', () => {
  it('suppresses when the server just pruned the errored track', () => {
    expect(shouldSuppressPrunedSkip(42, 42, T0, T0 + 500)).toBe(true);
  });

  it('does not suppress a skip for a different track', () => {
    expect(shouldSuppressPrunedSkip(42, 7, T0, T0 + 500)).toBe(false);
  });

  it('does not suppress when no prune has been seen', () => {
    expect(shouldSuppressPrunedSkip(42, null, null, T0)).toBe(false);
  });

  it('does not suppress when the errored track is unknown', () => {
    expect(shouldSuppressPrunedSkip(null, 42, T0, T0 + 500)).toBe(false);
  });

  it('does not suppress once the prune hint is stale', () => {
    expect(
      shouldSuppressPrunedSkip(42, 42, T0, T0 + PRUNE_SUPPRESSION_WINDOW_MS)
    ).toBe(false);
  });

  it('suppresses just inside the freshness window', () => {
    expect(
      shouldSuppressPrunedSkip(42, 42, T0, T0 + PRUNE_SUPPRESSION_WINDOW_MS - 1)
    ).toBe(true);
  });
});
