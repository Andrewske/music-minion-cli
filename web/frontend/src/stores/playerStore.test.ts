import { afterEach, describe, expect, it, vi } from 'vitest';
import { playFromPosition, usePlayerStore } from './playerStore';
import type { Track } from '@music-minion/shared';

const track: Track = { id: 2, title: 'B', duration: 300 } as Track;
const context = { type: 'comparison' as const, track_ids: [1, 2], shuffle: false };
const original = usePlayerStore.getState();

function stubPlay(): ReturnType<typeof vi.fn> {
  const play = vi.fn(async () => {});
  usePlayerStore.setState({ play });
  return play;
}

describe('playFromPosition', () => {
  afterEach(() => {
    usePlayerStore.setState({ play: original.play });
  });

  it('asks the server to start at the position, with no follow-up seek', async () => {
    const play = stubPlay();
    await playFromPosition(track, context, 90_000);
    expect(play).toHaveBeenCalledWith(track, context, { startPositionMs: 90_000 });
  });

  it('clamps past the end of a shorter track', async () => {
    const play = stubPlay();
    await playFromPosition(track, context, 400_000);
    expect(play).toHaveBeenCalledWith(track, context, { startPositionMs: 299_000 });
  });

  it('starts from zero for unknown durations and negative positions', async () => {
    const play = stubPlay();
    await playFromPosition({ ...track, duration: undefined }, context, 50_000);
    await playFromPosition(track, context, -5);
    expect(play).toHaveBeenNthCalledWith(1, expect.anything(), context, { startPositionMs: 0 });
    expect(play).toHaveBeenNthCalledWith(2, expect.anything(), context, { startPositionMs: 0 });
  });
});
