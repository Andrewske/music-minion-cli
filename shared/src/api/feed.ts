import { getDefaultApiClient } from './client';

// === Types ===

export type FeedRating = -1 | 0 | 1;

export type FeedItemStatus = 'visible' | 'hidden' | 'dismissed' | 'liked';

export interface FeedArtist {
  id: number;
  display_name: string | null;
  slug: string;
  avatar_url: string | null;
  in_top_200: boolean;
  in_library: boolean;
}

export interface FeedItem {
  id: number;
  local_track_id: number | null;
  soundcloud_id: string;
  title: string | null;
  artwork_url: string | null;
  permalink_url: string | null;
  duration_ms: number;
  uploaded_at: string;
  status: FeedItemStatus;
  in_likes: boolean;
  in_playlists: boolean;
  artist: FeedArtist;
}

export interface FeedPage {
  items: FeedItem[];
  next_cursor: string | null;
}

export interface GetFeedParams {
  cursor?: string;
  limit?: number;
  top200?: boolean;
  inLibrary?: boolean;
}

export interface RateFeedItemResponse {
  id: number;
  status: FeedItemStatus;
}

// === API Functions ===

export async function getFeed(params: GetFeedParams = {}): Promise<FeedPage> {
  const queryParams = new URLSearchParams();
  if (params.cursor) queryParams.set('cursor', params.cursor);
  if (params.limit) queryParams.set('limit', String(params.limit));
  if (params.top200) queryParams.set('top200', 'true');
  if (params.inLibrary) queryParams.set('in_library', 'true');

  const query = queryParams.toString();
  return getDefaultApiClient().request<FeedPage>(`/feed${query ? `?${query}` : ''}`);
}

export async function rateFeedItem(
  id: number,
  value: FeedRating
): Promise<RateFeedItemResponse> {
  return getDefaultApiClient().post<RateFeedItemResponse>(`/feed/${id}/rate`, { value });
}

/** One-time backfill: all followed artists, uploads since Jan 2026. Runs in
 * the background — poll getFeedSyncStatus() uploads_* fields for progress. */
export async function startFeedBackfill(): Promise<{ started: boolean }> {
  return getDefaultApiClient().post<{ started: boolean }>('/feed/backfill');
}
