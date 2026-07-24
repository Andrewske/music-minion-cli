/**
 * Playback error POLICY — pure decision logic shared by web and mobile.
 *
 * Owns the sliding error window (timestamps), the circuit breaker
 * (>= ERROR_THRESHOLD errors within ERROR_WINDOW_MS), and the
 * retry-once-per-playthrough decision. No platform imports; callers keep
 * their own retry MECHANICS (web: in-place <audio> re-resolve, mobile:
 * re-set the RNTP media item) and their own "already retried" ref.
 *
 * Lifecycle contract (mirrors web's original inline logic):
 * - On every playback error: `recordError(state, now)` FIRST, then `decidePlaybackError`.
 * - On successful playback (web `canplay`, mobile `Ready`): `clearErrorWindow()`
 *   so the window self-recovers.
 * - On track change (new playthrough): caller resets its already-retried id
 *   so every track gets one retry before skipping.
 */

export const ERROR_WINDOW_MS = 10_000;
export const ERROR_THRESHOLD = 3;

/** User-facing message when the breaker trips. Shared verbatim by web + mobile. */
export const PLAYBACK_BREAKER_MESSAGE = 'Playback unavailable — check connection';

export type PlaybackErrorDecision = 'retry' | 'skip' | 'breaker';

export interface ErrorWindowState {
  readonly errorTimes: readonly number[];
}

export const initialErrorWindow: ErrorWindowState = { errorTimes: [] };

/** Slide the window forward and record a new error at `now`. */
export function recordError(state: ErrorWindowState, now: number): ErrorWindowState {
  return {
    errorTimes: state.errorTimes.filter((t) => now - t < ERROR_WINDOW_MS).concat(now),
  };
}

/** Successful playback resets the window (breaker self-recovers). */
export function clearErrorWindow(): ErrorWindowState {
  return initialErrorWindow;
}

export function isBreakerTripped(state: ErrorWindowState): boolean {
  return state.errorTimes.length >= ERROR_THRESHOLD;
}

/**
 * Decide what to do about a playback error (call recordError first).
 *
 * - 'breaker': too many errors in the window — surface a persistent error,
 *   do NOT retry or skip (stops the runaway skip cascade).
 * - 'retry':   `trackId` is retryable (non-null) and has not had its one
 *   in-place retry this playthrough.
 * - 'skip':    advance to the next track.
 *
 * Pass `trackId: null` when the current track cannot be retried (unknown
 * track, or platform-specific guards fail — e.g. web's dataset.trackId
 * mismatch during a swap).
 */
export function decidePlaybackError(
  state: ErrorWindowState,
  trackId: number | null,
  alreadyRetriedTrackId: number | null,
): PlaybackErrorDecision {
  if (isBreakerTripped(state)) return 'breaker';
  if (trackId != null && trackId !== alreadyRetriedTrackId) return 'retry';
  return 'skip';
}

/**
 * A server prune hint is only fresh enough to suppress a pending error-skip
 * for this long. Guards against a stale lastPrunedTrackId suppressing a
 * legitimate skip if the same track ever errors again much later.
 */
export const PRUNE_SUPPRESSION_WINDOW_MS = 10_000;

/**
 * Should a pending error-skip be suppressed because the server already
 * pruned the errored track from the queue (and advanced past it)?
 *
 * When a track dies, the server marks it, prunes it, advances, and
 * broadcasts `playback:state` with a `pruned_track_id` hint. Meanwhile the
 * client's own error handler has a debounced skip timer pending; letting it
 * fire next() after the broadcast lands would double-advance and skip a
 * good track. Timer callbacks call this at FIRE time with fresh store state.
 */
export function shouldSuppressPrunedSkip(
  erroredTrackId: number | null,
  lastPrunedTrackId: number | null,
  lastPrunedAt: number | null,
  now: number,
): boolean {
  return (
    erroredTrackId != null
    && erroredTrackId === lastPrunedTrackId
    && lastPrunedAt != null
    && now - lastPrunedAt < PRUNE_SUPPRESSION_WINDOW_MS
  );
}
