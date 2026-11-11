import { rebindOrganizerPlayback } from '@music-minion/shared';
import type { PlayContext } from '@music-minion/shared';

/** True when live playback is organizer context bound to this session. */
export function isPlaybackBoundTo(context: PlayContext | null, sessionId: string | undefined): boolean {
  return sessionId !== undefined && context?.type === 'organizer' && context.session_id === sessionId;
}

/**
 * After the loaded session changed from `leavingId` to `next`, move live
 * organizer playback onto `next` (current track keeps playing; the upcoming
 * queue becomes next's unassigned pool). Resolves true when the server rebound.
 */
export async function followSessionWithPlayback(
  context: PlayContext | null,
  leavingId: string | undefined,
  next: { id: string } | null
): Promise<boolean> {
  if (!next || !leavingId || next.id === leavingId) return false;
  if (!isPlaybackBoundTo(context, leavingId)) return false;
  const { rebound } = await rebindOrganizerPlayback(leavingId, next.id);
  return rebound;
}
