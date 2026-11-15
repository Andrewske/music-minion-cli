import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlayContext } from '@music-minion/shared';

import { followSessionWithPlayback } from './playbackRebind';

const { rebind } = vi.hoisted(() => ({
  rebind: vi.fn<(from: string, to: string) => Promise<{ rebound: boolean }>>(),
}));
vi.mock('@music-minion/shared', () => ({
  rebindOrganizerPlayback: (from: string, to: string): Promise<{ rebound: boolean }> => rebind(from, to),
}));

const bound: PlayContext = { type: 'organizer', session_id: 'old' };

describe('followSessionWithPlayback', () => {
  beforeEach(() => {
    rebind.mockReset();
    rebind.mockResolvedValue({ rebound: true });
  });

  it('rebinds playback bound to the session being left', async () => {
    await expect(followSessionWithPlayback(bound, 'old', { id: 'new' })).resolves.toBe(true);
    expect(rebind).toHaveBeenCalledWith('old', 'new');
  });

  it('reports the server answer', async () => {
    rebind.mockResolvedValue({ rebound: false });
    await expect(followSessionWithPlayback(bound, 'old', { id: 'new' })).resolves.toBe(false);
  });

  it('skips the call when playback is elsewhere or nothing changed', async () => {
    await expect(followSessionWithPlayback({ type: 'playlist' }, 'old', { id: 'new' })).resolves.toBe(false);
    await expect(followSessionWithPlayback(bound, 'old', { id: 'old' })).resolves.toBe(false);
    await expect(followSessionWithPlayback(bound, 'old', null)).resolves.toBe(false);
    await expect(followSessionWithPlayback(bound, undefined, { id: 'new' })).resolves.toBe(false);
    expect(rebind).not.toHaveBeenCalled();
  });
});
