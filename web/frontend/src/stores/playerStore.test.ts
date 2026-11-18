import { afterEach, describe, expect, it, vi } from 'vitest';
import { playFromPosition, usePlayerStore } from './playerStore';
import type { Track } from '@music-minion/shared';

const track: Track = { id: 2, title: 'B', duration: 300 } as Track;
const context = { type: 'comparison' as const, track_ids: [1, 2], shuffle: false };
const original = usePlayerStore.getState();

/** play() that lands the new track like the WebSocket broadcast would: later. */
function stubPlayer(arrives: boolean): { seek: ReturnType<typeof vi.fn> } {
  const seek = vi.fn(async () => {});
  const play = vi.fn(async (t: Track) => {
    if (arrives) setTimeout(() => usePlayerStore.setState({ currentTrack: t }), 10);
  });
  usePlayerStore.setState({ currentTrack: { id: 1, title: 'A' } as Track, play, seek });
  return { seek };
}

describe('playFromPosition', () => {
  afterEach(() => {
    vi.useRealTimers();
    usePlayerStore.setState({ currentTrack: null, play: original.play, seek: original.seek });
  });

  it('seeks only after the new track becomes current', async () => {
    const { seek } = stubPlayer(true);
    const done = playFromPosition(track, context, 90_000);
    await Promise.resolve();
    expect(seek).not.toHaveBeenCalled();
    await done;
    expect(seek).toHaveBeenCalledWith(90_000);
  });

  it('clamps past the end of a shorter track', async () => {
    const { seek } = stubPlayer(true);
    await playFromPosition(track, context, 400_000);
    expect(seek).toHaveBeenCalledWith(299_000);
  });

  it('skips the seek when starting from zero', async () => {
    const { seek } = stubPlayer(true);
    await playFromPosition(track, context, 0);
    expect(seek).not.toHaveBeenCalled();
  });

  it('gives up without seeking if the track never arrives', async () => {
    vi.useFakeTimers();
    const { seek } = stubPlayer(false);
    const done = playFromPosition(track, context, 90_000);
    await vi.advanceTimersByTimeAsync(6000);
    await done;
    expect(seek).not.toHaveBeenCalled();
  });
});
