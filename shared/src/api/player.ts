/**
 * Player API — portable layer (no DOM dependencies).
 *
 * playback:state WebSocket broadcasts are slim (no queue array). When the
 * broadcast `queueVersion` moves past the version a client holds, the store
 * refetches the queue window through this endpoint.
 */
import type { Track } from './builder';

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
