import { getDefaultApiClient } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FirstLovedTrack {
  track_id: number;
  title: string;
  artist: string;
  loved_at: string;
}

export interface ArtistStats {
  id: number | null;
  soundcloud_user_id: string | null;
  display_name: string;
  slug: string | null;
  avatar_url: string | null;
  follower_count: number | null;
  is_following: boolean;
  ranking: number | null;
  in_top_200: boolean;
  hit_rate: number | null;
  tracks_seen: number;
  library_track_count: number;
  repost_in_library_count: number;
  feed_noise_7d: number;
  feed_noise_30d: number;
  last_loved_at: string | null;
  first_loved_track: FirstLovedTrack | null;
  avg_elo: number | null;
  last_activity_at: string | null;
  activity_state: 'active' | 'silent' | 'dormant';
}

export interface FeedEvent {
  track_sc_id: string;
  track_title: string;
  track_artist_name: string;
  seen_at: string;
  reposted_at: string | null;
}

export interface LibraryTrack {
  id: number;
  title: string;
  artist: string;
  album: string | null;
  genre: string | null;
  year: number | null;
  duration: number | null;
  local_path: string | null;
  play_count: number;
}

export interface MatchOverride {
  id: number;
  local_artist_name: string;
  action: 'merge' | 'split';
  created_at: string;
}

export interface ArtistDetail {
  artist: ArtistStats;
  recent_feed_events: FeedEvent[];
  top_library_tracks: LibraryTrack[];
  match_overrides: MatchOverride[];
}

export interface ParetoResult {
  artists_producing_80pct: number;
  total_events: number;
  threshold_ids: number[];
}

export interface FeedSyncState {
  [key: string]: unknown;
}

export interface UnfollowResult {
  unfollowed: boolean;
  sc_called: boolean;
  feed_events_deleted: number;
}

export interface FollowingsSyncResult {
  followings_synced: number;
  new_artists: number;
  unfollowed_remotely: number;
}

export interface GetArtistsOptions {
  source?: 'all' | 'soundcloud' | 'local' | 'following';
  sort?: string;
}

export interface CreateMatchOverrideBody {
  discovery_artist_id: number;
  local_artist_name: string;
  action: 'merge' | 'split';
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const artistsBase = (): string => `${getDefaultApiClient().getBaseUrl()}/artists`;

async function parseErrorResponse(response: Response, fallback: string): Promise<never> {
  const errorText = await response.text();
  try {
    const error = JSON.parse(errorText) as { detail?: string };
    throw new Error(error.detail ?? fallback);
  } catch (e) {
    if (e instanceof SyntaxError) {
      throw new Error(`${fallback}: ${response.status} ${errorText.substring(0, 100)}`);
    }
    throw e;
  }
}

// ---------------------------------------------------------------------------
// Fetch functions
// ---------------------------------------------------------------------------

export async function getArtists(opts: GetArtistsOptions = {}): Promise<ArtistStats[]> {
  const params = new URLSearchParams();
  if (opts.source) params.set('source', opts.source);
  if (opts.sort) params.set('sort', opts.sort);
  const qs = params.toString();
  const url = `${artistsBase()}${qs ? `?${qs}` : ''}`;
  const response = await fetch(url);
  if (!response.ok) await parseErrorResponse(response, 'Failed to fetch artists');
  return response.json() as Promise<ArtistStats[]>;
}

export async function getArtist(id: number): Promise<ArtistDetail> {
  const response = await fetch(`${artistsBase()}/${id}`);
  if (!response.ok) await parseErrorResponse(response, 'Failed to fetch artist');
  return response.json() as Promise<ArtistDetail>;
}

export async function unfollowArtist(id: number): Promise<UnfollowResult> {
  const response = await fetch(`${artistsBase()}/${id}/unfollow`, { method: 'POST' });
  if (!response.ok) await parseErrorResponse(response, 'Failed to unfollow artist');
  return response.json() as Promise<UnfollowResult>;
}

export async function createMatchOverride(body: CreateMatchOverrideBody): Promise<MatchOverride> {
  const response = await fetch(`${artistsBase()}/match-override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) await parseErrorResponse(response, 'Failed to create match override');
  return response.json() as Promise<MatchOverride>;
}

export async function deleteMatchOverride(overrideId: number): Promise<void> {
  const response = await fetch(`${artistsBase()}/match-override/${overrideId}`, {
    method: 'DELETE',
  });
  if (!response.ok) await parseErrorResponse(response, 'Failed to delete match override');
}

export async function getPareto(): Promise<ParetoResult> {
  const response = await fetch(`${artistsBase()}/pareto`);
  if (!response.ok) await parseErrorResponse(response, 'Failed to fetch pareto data');
  return response.json() as Promise<ParetoResult>;
}

export async function syncFollowings(): Promise<FollowingsSyncResult> {
  const response = await fetch(`${getDefaultApiClient().getBaseUrl()}/soundcloud/followings-sync`, {
    method: 'POST',
  });
  if (!response.ok) await parseErrorResponse(response, 'Failed to sync followings');
  return response.json() as Promise<FollowingsSyncResult>;
}

export async function syncFeed(): Promise<FeedSyncState> {
  const response = await fetch(`${getDefaultApiClient().getBaseUrl()}/soundcloud/feed-sync`, {
    method: 'POST',
  });
  if (!response.ok) await parseErrorResponse(response, 'Failed to sync feed');
  return response.json() as Promise<FeedSyncState>;
}

export async function getFeedSyncStatus(): Promise<FeedSyncState> {
  const response = await fetch(`${getDefaultApiClient().getBaseUrl()}/soundcloud/feed-sync/status`);
  if (!response.ok) await parseErrorResponse(response, 'Failed to fetch feed sync status');
  return response.json() as Promise<FeedSyncState>;
}
