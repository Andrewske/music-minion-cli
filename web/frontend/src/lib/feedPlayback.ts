import type { Track } from '@music-minion/shared';
import { materializeFeedItems } from '../api/feed';

/** The fields a SoundCloud row (feed, reviewed, flagged, stories) needs to be played on its own. */
export interface PlayableFeedRow {
  soundcloud_id: string;
  local_track_id: number | null;
  title: string | null;
  artist_name: string | null;
  duration_ms: number;
}

export function rowToTrack(item: PlayableFeedRow, localTrackId: number): Track {
  return {
    id: localTrackId,
    title: item.title ?? 'Untitled',
    artist: item.artist_name ?? 'Unknown artist',
    duration: item.duration_ms / 1000,
  };
}

/**
 * The row's library track id, creating its streaming-only track first when it
 * has none. Null when materialization fails.
 */
export async function resolveLocalTrackId(item: PlayableFeedRow): Promise<number | null> {
  if (item.local_track_id !== null) return item.local_track_id;
  const created = await materializeFeedItems([item.soundcloud_id]).catch(() => []);
  return created[0]?.local_track_id ?? null;
}
