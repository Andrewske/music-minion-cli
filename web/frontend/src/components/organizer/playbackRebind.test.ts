import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlayContext } from '@music-minion/shared';
import { rebindOrganizerPlayback } from '@music-minion/shared';
import { followSessionWithPlayback, isPlaybackBoundTo } from './playbackRebind';

vi.mock('@music-minion/shared', () => ({ rebindOrganizerPlayback: vi.fn() }));

const rebindMock = vi.mocked(rebindOrganizerPlayback);
const organizer = (sessionId: string): PlayContext => ({ type: 'organizer', playlist_id: 1, session_id: sessionId });

describe('followSessionWithPlayback', () => {
  beforeEach(() => {
    rebindMock.mockReset();
    rebindMock.mockResolvedValue({ rebound: true });
  });

  it('rebinds when organizer playback is on the session being left', async () => {
    await expect(followSessionWithPlayback(organizer('s1'), 's1', { id: 's2' })).resolves.toBe(true);
    expect(rebindMock).toHaveBeenCalledWith('s1', 's2');
  });

  it('reports the server answer when nothing was rebound', async () => {
    rebindMock.mockResolvedValue({ rebound: false });
    await expect(followSessionWithPlayback(organizer('s1'), 's1', { id: 's2' })).resolves.toBe(false);
  });

  it.each<[string, PlayContext | null, string | undefined, { id: string } | null]>([
    ['no playback', null, 's1', { id: 's2' }],
    ['playlist playback', { type: 'playlist', playlist_id: 1 }, 's1', { id: 's2' }],
    ['organizer on another session', organizer('s9'), 's1', { id: 's2' }],
    ['no new session (deleted a parked one)', organizer('s1'), 's1', null],
    ['same session', organizer('s1'), 's1', { id: 's1' }],
  ])('does nothing with %s', async (_label, context, leavingId, next) => {
    await expect(followSessionWithPlayback(context, leavingId, next)).resolves.toBe(false);
    expect(rebindMock).not.toHaveBeenCalled();
  });

  it('isPlaybackBoundTo needs a session id', () => {
    expect(isPlaybackBoundTo(organizer('s1'), undefined)).toBe(false);
  });
});
