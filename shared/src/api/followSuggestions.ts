import { getDefaultApiClient } from './client';

/** Counts behind a suggestion's score, one per credit role. */
export interface SuggestionEvidence {
  uploaded: number;
  original: number;
  remixer: number;
  feat: number;
  remixed_by_others: number;
  kept: number;
}

export interface SuggestionActivity {
  uploads_90d: number;
  reposts_90d: number;
  last_active_at: string | null;
}

export type SuggestionRole = keyof SuggestionEvidence;

export interface SuggestionTrack {
  soundcloud_id: string;
  title: string;
  artist: string;
  role: SuggestionRole;
  liked_at: string | null;
}

export interface Suggestion {
  /** SC user id, or "name:<name_key>" when unresolved. */
  key: string;
  /** Null for an unresolved name: no follow button, link to SoundCloud search instead. */
  soundcloud_user_id: string | null;
  display_name: string;
  permalink: string | null;
  avatar_url: string | null;
  followers: number | null;
  is_label: boolean;
  score: number;
  evidence: SuggestionEvidence;
  last_liked_at: string | null;
  activity: SuggestionActivity | null;
  /** Up to 20, newest like first. */
  tracks: SuggestionTrack[];
}

export interface FollowSuggestionsResponse {
  artists: Suggestion[];
  labels: Suggestion[];
  generated_at: string;
}

export interface UntieredArtist {
  discovery_artist_id: number;
  display_name: string;
  slug: string;
  avatar_url: string | null;
  /** null when untiered; 'C' for an automatic tier on a new follow. */
  tier: string | null;
  followed_at: string | null;
  follow_order: number | null;
  rated_count: number;
  keep_rate: number | null;
}

export interface UntieredResponse {
  /** Newest follows that are untiered or still on their automatic tier C. */
  recent: UntieredArtist[];
  /** Untiered with >= 3 rated tracks, by keep_rate desc. */
  rated: UntieredArtist[];
}

export interface ConnectionVia {
  discovery_artist_id: number;
  display_name: string;
  tier: string;
  relation: 'collab' | 'remix' | 'feat' | 'follows';
}

export interface FollowConnection {
  key: string;
  soundcloud_user_id: string | null;
  display_name: string;
  permalink: string | null;
  avatar_url: string | null;
  followers: number | null;
  score: number;
  via: ConnectionVia[];
}

export interface FollowConnectionsResponse {
  co_credit: FollowConnection[];
  favorites_follow: FollowConnection[];
}

export interface OkResponse {
  ok: true;
}

export interface FollowAccountResponse {
  ok: true;
  discovery_artist_id: number;
}

const BASE = '/follow-suggestions';
const keyPath = (key: string): string => `${BASE}/${encodeURIComponent(key)}`;

export async function getFollowSuggestions(): Promise<FollowSuggestionsResponse> {
  return getDefaultApiClient().request<FollowSuggestionsResponse>(BASE);
}

/** Permanent: the account never comes back as a suggestion. */
export async function dismissSuggestion(key: string): Promise<OkResponse> {
  return getDefaultApiClient().post<OkResponse>(`${keyPath(key)}/dismiss`);
}

export async function setSuggestionLabel(key: string, isLabel: boolean): Promise<OkResponse> {
  return getDefaultApiClient().post<OkResponse>(`${keyPath(key)}/label`, { is_label: isLabel });
}

export async function getUntieredFollows(): Promise<UntieredResponse> {
  return getDefaultApiClient().request<UntieredResponse>(`${BASE}/untiered`);
}

/** Follows on SoundCloud and adds the account at tier C. */
export async function followAccount(soundcloudUserId: string): Promise<FollowAccountResponse> {
  return getDefaultApiClient().post<FollowAccountResponse>(`${keyPath(soundcloudUserId)}/follow`);
}

export async function getFollowConnections(): Promise<FollowConnectionsResponse> {
  return getDefaultApiClient().request<FollowConnectionsResponse>(`${BASE}/connections`);
}
