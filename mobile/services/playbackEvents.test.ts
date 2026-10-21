import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const setMediaItem = vi.fn();
const next = vi.fn();
const setPlaybackError = vi.fn();
const storeState = {
  currentTrack: { id: 7, title: 'Dead Track', artist: 'A', duration: 200 },
  isPlaying: true,
  lastPrunedTrackId: null,
  lastPrunedAt: null,
  next,
  setPlaybackError,
};

vi.mock('@rntp/player', () => ({
  default: { setMediaItem, play: vi.fn(), addEventListener: vi.fn() },
  Event: { PlaybackStateChanged: 'state', PlaybackError: 'error' },
  PlaybackState: { Ready: 'ready', Ended: 'ended' },
}));

vi.mock('../stores/playerStore', () => ({
  usePlayerStore: { getState: () => storeState },
}));

vi.mock('./e2eHooks', () => ({
  resolveStreamUrl: (id: number) => `http://test/tracks/${id}/stream`,
}));

vi.mock('@music-minion/shared', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@music-minion/shared')>();
  return {
    ...actual,
    getStreamUrl: (id: number) => `http://test/tracks/${id}/stream`,
    getDefaultApiClient: () => ({ getBaseUrl: () => 'http://test' }),
    probeStreamForReauth: vi.fn(async () => false),
  };
});

const errorEvent = { type: 'error', code: 'source', message: 'Source error' } as never;

describe('handlePlaybackEvent error path', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    setMediaItem.mockClear();
    next.mockClear();
    setPlaybackError.mockClear();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('escalates a fast retry failure (<1s) to banner + skip', async () => {
    const { handlePlaybackEvent, resetRetryTracking } = await import('./playbackEvents');
    resetRetryTracking();

    handlePlaybackEvent(errorEvent);
    await vi.advanceTimersByTimeAsync(10); // reauth probe resolves → retry
    expect(setMediaItem).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(300); // retry 404s quickly
    handlePlaybackEvent(errorEvent);
    await vi.advanceTimersByTimeAsync(10);
    expect(setPlaybackError).toHaveBeenCalledWith('Failed to load: Dead Track');

    await vi.advanceTimersByTimeAsync(2_000);
    expect(next).toHaveBeenCalledTimes(1);
  });

  it('still drops a duplicate delivery of the same error', async () => {
    const { handlePlaybackEvent, resetRetryTracking } = await import('./playbackEvents');
    resetRetryTracking();

    handlePlaybackEvent(errorEvent);
    handlePlaybackEvent(errorEvent); // same physical event, second listener
    await vi.advanceTimersByTimeAsync(10);

    expect(setMediaItem).toHaveBeenCalledTimes(1);
    expect(setPlaybackError).not.toHaveBeenCalled();
  });
});
