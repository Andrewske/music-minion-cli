import type {
  FollowConnection, FollowConnectionsResponse, FollowSuggestionsResponse, Suggestion, UntieredArtist,
  UntieredResponse,
} from '../../api/followSuggestions';

export function makeSuggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    key: '100',
    soundcloud_user_id: '100',
    display_name: 'Wooli',
    permalink: 'woolimusic',
    avatar_url: null,
    followers: 120_000,
    is_label: false,
    score: 9.5,
    evidence: { uploaded: 8, original: 4, remixer: 4, feat: 0, remixed_by_others: 0, kept: 0 },
    last_liked_at: null,
    activity: { uploads_90d: 6, reposts_90d: 6, last_active_at: null },
    tracks: [
      { soundcloud_id: 't1', title: 'Wobble', artist: 'Wooli', role: 'uploaded', liked_at: null },
      { soundcloud_id: 't2', title: 'Other (Wooli Remix)', artist: 'Someone', role: 'remixer', liked_at: null },
    ],
    ...overrides,
  };
}

export function makeResponse(artists: Suggestion[], labels: Suggestion[] = []): FollowSuggestionsResponse {
  return { artists, labels, generated_at: '2026-11-11T00:00:00Z' };
}

export function makeConnection(overrides: Partial<FollowConnection> = {}): FollowConnection {
  return {
    key: '300',
    soundcloud_user_id: '300',
    display_name: 'Collab Partner',
    permalink: 'collab-partner',
    avatar_url: null,
    followers: 5_000,
    score: 3,
    via: [{ discovery_artist_id: 1, display_name: 'Fav', tier: 'S', relation: 'collab' }],
    ...overrides,
  };
}

export function makeConnections(overrides: Partial<FollowConnectionsResponse> = {}): FollowConnectionsResponse {
  return { co_credit: [], favorites_follow: [], ...overrides };
}

export function makeUntiered(overrides: Partial<UntieredArtist> = {}): UntieredArtist {
  return {
    discovery_artist_id: 7,
    display_name: 'New Follow',
    slug: 'new-follow',
    avatar_url: null,
    followed_at: null,
    follow_order: 1,
    rated_count: 4,
    keep_rate: 0.5,
    ...overrides,
  };
}

export const EMPTY_UNTIERED: UntieredResponse = { recent: [], rated: [] };
