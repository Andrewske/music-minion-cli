/**
 * Player API — portable layer (no DOM dependencies).
 *
 * playback:state WebSocket broadcasts are slim (no queue array). When the
 * broadcast `queueVersion` moves past the version a client holds, the store
 * refetches the queue window through this endpoint.
 */
import type { Track } from './builder';
import { getDefaultApiClient } from './client';

export interface QueuePage {
  /** Server queue_version this page was cut from (monotonic). */
  version: number;
  /** Total tracks in the live queue. */
  total: number;
  offset: number;
  tracks: Track[];
}

/**
 * Fetch one page of the live playback queue.
 *
 * Takes an explicit apiBase (rather than the default client singleton) so the
 * player store can pass its injected base URL — same pattern as the store's
 * own POSTs — and both web and mobile share it.
 */
export async function fetchPlayerQueue(
  apiBase: string,
  offset = 0,
  limit = 100,
): Promise<QueuePage> {
  const response = await fetch(
    `${apiBase}/player/queue?offset=${offset}&limit=${limit}`,
  );
  if (!response.ok) {
    throw new Error(`Queue fetch failed: ${response.statusText}`);
  }
  return response.json() as Promise<QueuePage>;
}

export interface RebindOrganizerResponse {
  /** False when live playback wasn't bound to fromSessionId (nothing changed). */
  rebound: boolean;
}

/**
 * Move live organizer playback from one session to another of the same
 * playlist without restarting the current track. Safe to call when playback
 * isn't bound to fromSessionId: the server answers `{rebound: false}`.
 */
export async function rebindOrganizerPlayback(
  fromSessionId: string,
  toSessionId: string,
): Promise<RebindOrganizerResponse> {
  const response = await fetch(`${getDefaultApiClient().getBaseUrl()}/player/organizer/rebind`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fromSessionId, toSessionId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to rebind organizer playback');
  }
  return response.json() as Promise<RebindOrganizerResponse>;
}

/** Where an inserted track lands: right after the current one, or after the loaded window. */
export type QueueInsertPosition = 'next' | 'last';

export interface QueueInsertResponse {
  /** Queue index the track landed at. */
  index: number;
  queue_size: number;
}

/** Throws with the server's `detail` (e.g. "Nothing is playing") when the call fails. */
async function playerRequest<T>(url: string, init: RequestInit, fallback: string): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const error: { detail?: string } = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? `${fallback}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

const jsonPost = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/** Play next / add to queue without restarting playback (POST /player/queue). */
export function insertIntoQueue(
  apiBase: string,
  trackId: number,
  position: QueueInsertPosition,
): Promise<QueueInsertResponse> {
  return playerRequest(`${apiBase}/player/queue`, jsonPost({ trackId, position }), 'Queue insert failed');
}

/**
 * Jump to a queue position (POST /player/jump). trackId must be the track the
 * client sees at `index`; the server answers 409 when its queue moved on.
 */
export function jumpToQueueIndex(
  apiBase: string,
  index: number,
  trackId: number,
): Promise<{ queue_index: number }> {
  return playerRequest(`${apiBase}/player/jump`, jsonPost({ index, trackId }), 'Jump failed');
}

export interface ScLikeResponse {
  soundcloud_id: string;
  sc_liked: boolean;
}

/**
 * Like (PUT) or unlike (DELETE) a track on SoundCloud. Liking queues the same
 * durable job a feed Keep does, without recording a Keep verdict.
 */
export function setScLike(apiBase: string, soundcloudId: string, liked: boolean): Promise<ScLikeResponse> {
  const init: RequestInit = { method: liked ? 'PUT' : 'DELETE' };
  return playerRequest(`${apiBase}/soundcloud/likes/${encodeURIComponent(soundcloudId)}`, init, 'Like failed');
}
