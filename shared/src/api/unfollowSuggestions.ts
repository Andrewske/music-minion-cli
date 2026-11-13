import { getDefaultApiClient } from './client';
import type { FollowingCount, OkResponse } from './followSuggestions';

/** A followed account and the numbers behind suggesting an unfollow. */
export interface UnfollowCandidate {
  discovery_artist_id: number;
  soundcloud_user_id: string | null;
  display_name: string | null;
  slug: string;
  avatar_url: string | null;
  followers: number | null;
  /** S/A/B/C/D, or null when untiered. Tiered accounts are listed too. */
  tier: string | null;
  followed_at: string | null;
  /** Reposts + own uploads seen in the feed. */
  items: number;
  reposts: number;
  uploads: number;
  /** Distinct liked or kept tracks among those items. */
  good: number;
  /** Liked/kept reposts no other followed account carried. */
  unique_finds: number;
  liked_uploads: number;
  value: number;
  noise_per_month: number;
  last_find_at: string | null;
  last_item_at: string | null;
}

export type UnfollowSection = 'redundant' | 'dormant' | 'labels' | 'low_yield';

export interface UnfollowSuggestionsResponse {
  sections: Record<UnfollowSection, UnfollowCandidate[]>;
  following: FollowingCount;
  generated_at: string;
}

export interface UnfollowBatchResult {
  id: number;
  ok: boolean;
  status?: number;
  error?: string;
}

export interface UnfollowBatchResponse {
  /** In request order; ids after a stop are missing. */
  results: UnfollowBatchResult[];
  /** True when a SoundCloud-wide error (auth, rate limit, outage) ended the batch. */
  stopped: boolean;
  error: string | null;
}

export interface UnfollowAccountResponse {
  unfollowed: true;
  sc_called: boolean;
  reposts_removed: number;
}

/** The server refuses larger batches. */
export const UNFOLLOW_BATCH_SIZE = 25;

const BASE = '/unfollow-suggestions';

export async function getUnfollowSuggestions(): Promise<UnfollowSuggestionsResponse> {
  return getDefaultApiClient().request<UnfollowSuggestionsResponse>(BASE);
}

/** Permanent: never suggested again. An untiered account becomes tier C. */
export async function keepFollowing(id: number): Promise<OkResponse> {
  return getDefaultApiClient().post<OkResponse>(`${BASE}/${id}/keep`);
}

export async function unfollowSuggested(id: number): Promise<UnfollowAccountResponse> {
  return getDefaultApiClient().post<UnfollowAccountResponse>(`${BASE}/${id}/unfollow`);
}

/** Up to 25 ids, unfollowed in order on the server. */
export async function unfollowBatch(ids: number[]): Promise<UnfollowBatchResponse> {
  return getDefaultApiClient().post<UnfollowBatchResponse>(`${BASE}/unfollow-batch`, { ids });
}
