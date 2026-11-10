import { getDefaultApiClient } from './client';
import type { FeedActionStatus } from './feed';

/** Rolling window the Stories page asks for, in days. */
export const STORIES_WINDOW_DAYS = 7;

export type StoriesTrackKind = 'repost' | 'upload';
export type StoriesDecision = 'keep' | 'not_quite' | 'nope';

/** One repost or upload by a followed artist, inside the window. */
export interface StoriesTrack {
  soundcloud_id: string;
  title: string | null;
  /** The track's uploader (not the reposting artist). */
  artist_name: string | null;
  artwork_url: string | null;
  permalink_url: string | null;
  duration_ms: number;
  kind: StoriesTrackKind;
  /** ISO 8601 UTC. */
  activity_at: string;
  /** Null until materialized via POST /feed/materialize. */
  local_track_id: number | null;
  /** Jev keep probability, null when unscored. */
  score: number | null;
  /** The MM verdict only; a SoundCloud like is sc_liked, never a fabricated keep. */
  decision: StoriesDecision | null;
  /** Heard, decided, in the library, played, or liked on SoundCloud. */
  listened: boolean;
  /** In the user's SoundCloud likes. */
  sc_liked: boolean;
  /** Status of the keep's queued SoundCloud like job, null when there is none. */
  sc_like_action: FeedActionStatus;
}

export interface StoriesArtist {
  discovery_artist_id: number;
  display_name: string | null;
  slug: string;
  avatar_url: string | null;
  latest_activity_at: string;
  unheard_count: number;
  /** Server order: Jev score desc, unscored last, then activity desc. */
  tracks: StoriesTrack[];
}

export interface StoriesResponse {
  generated_at: string;
  /** Newest activity first; artists with zero unheard tracks are omitted. */
  artists: StoriesArtist[];
}

export interface StoryListenedResponse {
  soundcloud_id: string;
  listened: boolean;
}

export async function getStories(days: number = STORIES_WINDOW_DAYS): Promise<StoriesResponse> {
  return getDefaultApiClient().request<StoriesResponse>(`/stories?days=${days}`);
}

/** Idempotent: records that the track played >= 5s on the Stories page. */
export async function markStoryListened(soundcloudId: string): Promise<StoryListenedResponse> {
  return getDefaultApiClient().post<StoryListenedResponse>(
    `/stories/${encodeURIComponent(soundcloudId)}/listened`,
    { surface: 'stories' }
  );
}
