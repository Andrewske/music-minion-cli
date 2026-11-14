/**
 * Pure pieces of organizer session transitions: route/store sync, the
 * one-at-a-time transition lock, and recovery when a committed finish/delete
 * can't load its replacement.
 */

interface LoadedSessionLike {
  id: string;
  playlist_id: number;
}

/**
 * Session id the screen's route param + organizer store should move to, or
 * null when nothing needs syncing. Only a session of the screen's own playlist
 * counts, so a late result for another playlist never leaks into this screen.
 */
export function sessionToSync(
  loaded: LoadedSessionLike | undefined,
  routeSessionId: string | undefined,
  playlistId: number
): string | null {
  if (!loaded || loaded.playlist_id !== playlistId) return null;
  return loaded.id === routeSessionId ? null : loaded.id;
}

export interface TransitionLock {
  /** False when a transition is already running; the caller must not start another. */
  tryAcquire: () => boolean;
  release: () => void;
  isHeld: () => boolean;
}

/** Mutable one-slot lock (held in a ref), so two taps in one tick can't both start a transition. */
export function createTransitionLock(): TransitionLock {
  let held = false;
  return {
    tryAcquire: (): boolean => {
      if (held) return false;
      held = true;
      return true;
    },
    release: (): void => {
      held = false;
    },
    isHeld: (): boolean => held,
  };
}

/**
 * Run a server-side commit (finalize / discard), then load the replacement
 * session. The commit can't be rolled back, so if loading the replacement
 * fails, `onLost` runs first (drop the stale loaded session so nothing edits
 * it) and the error is rethrown for the caller to report.
 */
export async function commitThenReplace<T>(
  commit: () => Promise<void>,
  loadReplacement: () => Promise<T>,
  onLost: () => Promise<void>
): Promise<T> {
  await commit();
  try {
    return await loadReplacement();
  } catch (err) {
    await onLost();
    throw err;
  }
}
