/**
 * E2E-only test seams for Maestro flows (mobile/.maestro).
 *
 * Enabled ONLY when the bundle is built with EXPO_PUBLIC_E2E=1 (scripts/e2e.sh
 * sets it). Babel inlines the env var at build time, so in normal builds
 * E2E_ENABLED is the literal `false` and every seam is a no-op.
 *
 * Bad-stream seam: Maestro can't corrupt a stream URL from outside the app
 * (HTTPS, live backend), so a long-press on the Now Playing title arms
 * "break the next track that loads". That track's URL (initial load AND the
 * one in-place retry) points at a path the backend 404s, which drives the
 * real RNTP error → retry → skip path in services/playbackEvents.ts without
 * touching backend data (a 404 on an unknown route never prunes/marks tracks).
 */
import { getDefaultApiClient, getStreamUrl } from '@music-minion/shared';

export const E2E_ENABLED = process.env.EXPO_PUBLIC_E2E === '1';

let armed = false;
let brokenTrackId: number | null = null;

/** Arm the bad-stream seam: the next track to load gets an unplayable URL. */
export function armBadStream(): void {
  if (!E2E_ENABLED) return;
  armed = true;
  brokenTrackId = null;
}

/**
 * Stream URL for a track. Identical to getStreamUrl() unless the E2E
 * bad-stream seam is armed / has claimed this track.
 */
export function resolveStreamUrl(trackId: number): string {
  if (!E2E_ENABLED) return getStreamUrl(trackId);
  if (armed) {
    armed = false;
    brokenTrackId = trackId;
  }
  if (trackId !== brokenTrackId) return getStreamUrl(trackId);
  return `${getDefaultApiClient().getBaseUrl()}/e2e-broken-stream/${trackId}`;
}
