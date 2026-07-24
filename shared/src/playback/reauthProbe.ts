/**
 * SoundCloud reauth detection — shared by web and mobile.
 *
 * Audio elements / RNTP surface playback errors without an HTTP status, so a
 * revoked SoundCloud refresh token (backend 503s every SC stream with detail
 * "soundcloud_reauth_required") looks like any other dead track. Auto-skipping
 * would 503-walk the entire SC queue. Instead, on playback error the platforms
 * probe the stream URL FIRST (short timeout) and surface a persistent
 * "re-authenticate" message when the 503 detail matches — no retry, no skip,
 * and the error does NOT count toward the sliding error window.
 *
 * The probe is best-effort: any failure (timeout, network, parse) or non-503
 * answer returns false so callers fall back to the normal error policy.
 */

export const SOUNDCLOUD_REAUTH_DETAIL = 'soundcloud_reauth_required';

/** User-facing persistent message. Distinct from PLAYBACK_BREAKER_MESSAGE. */
export const SOUNDCLOUD_REAUTH_MESSAGE = 'SoundCloud session expired — re-authenticate';

export const REAUTH_PROBE_TIMEOUT_MS = 3_000;

/** Pure check: does a parsed 503 JSON body carry the reauth detail? */
export function isReauthDetail(body: unknown): boolean {
  if (typeof body !== 'object' || body === null) return false;
  return (body as Record<string, unknown>).detail === SOUNDCLOUD_REAUTH_DETAIL;
}

/**
 * GET the stream URL and report whether it 503s with the reauth detail.
 *
 * A plain GET (redirects followed) is used because the endpoint mixes
 * FileResponse (local) and RedirectResponse (SoundCloud) and may not support
 * HEAD; the request is aborted as soon as a non-503 status arrives so no
 * audio body is downloaded. The 503 error body itself is a tiny JSON object.
 */
export async function probeStreamForReauth(
  streamUrl: string,
  timeoutMs: number = REAUTH_PROBE_TIMEOUT_MS,
): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(streamUrl, { signal: controller.signal });
    if (res.status !== 503) {
      controller.abort();
      return false;
    }
    const body: unknown = await res.json().catch(() => null);
    return isReauthDetail(body);
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
