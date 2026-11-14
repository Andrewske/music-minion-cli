/**
 * Move live organizer playback onto the newly loaded session after a switch.
 * Mirrors web/frontend/src/components/organizer/playbackRebind.ts.
 */
import { rebindOrganizerPlayback } from '@music-minion/shared';
import type { PlayContext } from '@music-minion/shared';
import { shouldRebindPlayback } from './sessionSwitcher';

/**
 * After the loaded session changed from `leavingId` to `next`: if playback was
 * organizer context bound to the old session, the current track keeps playing
 * and the upcoming queue becomes next's unassigned pool. Resolves true when
 * the server rebound.
 */
export async function followSessionWithPlayback(
  context: PlayContext | null,
  leavingId: string | undefined,
  next: { id: string } | null
): Promise<boolean> {
  if (!next || !leavingId || !shouldRebindPlayback(context, leavingId, next)) return false;
  const { rebound } = await rebindOrganizerPlayback(leavingId, next.id);
  return rebound;
}
