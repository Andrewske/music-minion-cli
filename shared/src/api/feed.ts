import { getDefaultApiClient } from './client';

export const FEED_PAGE_SIZE = 100;
export const FEED_RANK_PRESETS = [25, 50, 75, 100, 200] as const;

export type FeedSource = 'all' | 'releases' | 'reposts';
export type FeedRankPreset = (typeof FEED_RANK_PRESETS)[number];
export type FeedRating = -1 | 0 | 1;
export type FeedDecision = 'keep' | 'nope' | 'hide';
export type FeedItemStatus = 'visible' | 'hidden' | 'dismissed' | 'liked';
/** Mirrors sc_feed_action_jobs.status; 'running' is a claimed-but-unfinished job. */
export type FeedActionStatus = 'pending' | 'running' | 'complete' | 'error' | null;

export interface FeedArtist {
  /** Discovery-artist id, when the backend has a local artist record. */
  id: number;
  soundcloud_id: string | null;
  display_name: string | null;
  slug: string;
  avatar_url: string | null;
  ranking: number | null;
  in_library?: boolean;
  /** Deprecated; use ranking with max_rank. */
  in_top_200?: boolean;
  /** Present on reposters only. */
  reposted_at?: string | null;
  repost_time_precision?: string | null;
}

export interface FeedActionState {
  like: FeedActionStatus;
  monthly_playlist: FeedActionStatus;
  error: string | null;
}

export interface FeedItem {
  /** Canonically the SoundCloud id. Older servers may return a numeric upload id. */
  id: string | number;
  local_track_id: number | null;
  soundcloud_id: string;
  title: string | null;
  artwork_url: string | null;
  permalink_url: string | null;
  duration_ms: number;
  genre: string | null;
  access?: string | null;
  event_at: string;
  uploaded_at: string | null;
  released_at: string | null;
  sources: Array<'release' | 'repost'>;
  uploader: FeedArtist | null;
  reposters: FeedArtist[];
  best_reposter_rank: number | null;
  reposter_count: number;
  current_decision: FeedDecision | null;
  decided_at: string | null;
  action_state: FeedActionState;
  keep_probability: number | null;
  prediction_model_version: string | null;
  prediction_explanation: string | null;

  /** Compatibility fields returned by the release-only API. */
  status?: FeedItemStatus;
  in_likes?: boolean;
  in_playlists?: boolean;
  artist?: FeedArtist;
  decision?: FeedDecision | null;
}

export interface FeedPage {
  items: FeedItem[];
  next_cursor: string | null;
}

export interface GetFeedParams {
  cursor?: string;
  limit?: number;
  source?: FeedSource;
  maxRank?: FeedRankPreset;
  inLibrary?: boolean;
  showHidden?: boolean;
}

export interface RateFeedItemOptions {
  surface?: 'web' | 'mobile' | string;
  modelVersion?: string;
  featureSnapshot?: Record<string, unknown>;
}

export interface RateFeedItemResponse {
  soundcloud_id: string;
  current_decision: FeedDecision;
  decided_at: string;
  local_track_id: number | null;
  action_state: FeedActionState;
  /** Compatibility with servers using the shorter field name. */
  decision?: FeedDecision;
}

export interface MaterializeFeedItemResponse {
  soundcloud_id: string;
  local_track_id: number;
}

export const feedRatingToDecision = (rating: FeedRating): FeedDecision => {
  if (rating === 1) return 'keep';
  if (rating === -1) return 'nope';
  return 'hide';
};

export const getFeedItemDecision = (item: FeedItem): FeedDecision | null => {
  if (item.current_decision !== undefined) return item.current_decision;
  if (item.decision !== undefined) return item.decision;
  if (item.status === 'liked') return 'keep';
  if (item.status === 'dismissed') return 'nope';
  if (item.status === 'hidden') return 'hide';
  return null;
};

export const getFeedItemUploader = (item: FeedItem): FeedArtist | null =>
  item.uploader ?? item.artist ?? null;

export const getFeedEventAt = (item: FeedItem): string =>
  item.event_at || item.released_at || item.uploaded_at || '';

export const getFeedItemBestRank = (item: FeedItem): number | null => {
  const uploaderRank = item.sources.includes('release')
    ? getFeedItemUploader(item)?.ranking ?? null
    : null;
  const reposterRanks = item.sources.includes('repost')
    ? [item.best_reposter_rank, ...item.reposters.map((reposter) => reposter.ranking)]
    : [];
  const ranks = [uploaderRank, ...reposterRanks]
    .filter((rank): rank is number => rank !== null && rank !== undefined);
  return ranks.length > 0 ? Math.min(...ranks) : null;
};

const normalizeFeedArtist = (artist: FeedArtist | null | undefined): FeedArtist | null =>
  artist
    ? {
        ...artist,
        soundcloud_id: artist.soundcloud_id ?? null,
        ranking: artist.ranking ?? null,
      }
    : null;

/** Normalize release-only responses during rolling web/backend deployments. */
export const normalizeFeedItem = (item: FeedItem): FeedItem => {
  const uploader = normalizeFeedArtist(item.uploader ?? item.artist);
  return {
    ...item,
    genre: item.genre ?? null,
    event_at: item.event_at || item.released_at || item.uploaded_at || '',
    uploaded_at: item.uploaded_at ?? null,
    released_at: item.released_at ?? item.uploaded_at ?? null,
    sources: item.sources?.length ? item.sources : ['release'],
    uploader,
    reposters: (item.reposters ?? []).map((reposter) => normalizeFeedArtist(reposter) as FeedArtist),
    best_reposter_rank: item.best_reposter_rank ?? null,
    reposter_count: item.reposter_count ?? item.reposters?.length ?? 0,
    current_decision: getFeedItemDecision(item),
    decided_at: item.decided_at ?? null,
    action_state: item.action_state ?? { like: null, monthly_playlist: null, error: null },
    keep_probability: item.keep_probability ?? null,
    prediction_model_version: item.prediction_model_version ?? null,
    prediction_explanation: item.prediction_explanation ?? null,
  };
};

export const applyFeedDecision = (
  item: FeedItem,
  decision: FeedDecision
): FeedItem => ({
  ...item,
  current_decision: decision,
  status:
    decision === 'keep' ? 'liked' : decision === 'nope' ? 'dismissed' : 'hidden',
  action_state:
    decision === 'keep'
      ? { like: 'pending', monthly_playlist: 'pending', error: null }
      : item.action_state,
});

export const mergeFeedDecisionResponse = (
  item: FeedItem,
  response: RateFeedItemResponse
): FeedItem => ({
  ...item,
  local_track_id: response.local_track_id ?? item.local_track_id,
  current_decision: response.current_decision ?? response.decision ?? item.current_decision,
  decided_at: response.decided_at,
  action_state: response.action_state,
});

const SYNC_IN_FLIGHT: ReadonlySet<FeedActionStatus> = new Set(['pending', 'running']);

/** A keep whose SoundCloud like or playlist add has not finished yet. */
export const isFeedSyncPending = (state: FeedActionState | null | undefined): boolean =>
  !!state && (SYNC_IN_FLIGHT.has(state.like) || SYNC_IN_FLIGHT.has(state.monthly_playlist));

/** A keep whose SoundCloud side failed; the local decision still stands. */
export const isFeedSyncFailed = (state: FeedActionState | null | undefined): boolean =>
  !!state && (state.like === 'error' || state.monthly_playlist === 'error');

export const hasPendingFeedSync = (
  pages: ReadonlyArray<{ items: FeedItem[] }> | undefined
): boolean =>
  pages?.some((page) => page.items.some((item) => isFeedSyncPending(item.action_state))) ?? false;

export async function getFeed(params: GetFeedParams = {}): Promise<FeedPage> {
  const queryParams = new URLSearchParams();
  if (params.cursor) queryParams.set('cursor', params.cursor);
  queryParams.set('limit', String(params.limit ?? FEED_PAGE_SIZE));
  if (params.source) queryParams.set('source', params.source);
  if (params.maxRank) queryParams.set('max_rank', String(params.maxRank));
  if (params.inLibrary) queryParams.set('in_library', 'true');
  if (params.showHidden) queryParams.set('show_hidden', 'true');

  const page = await getDefaultApiClient().request<FeedPage>(`/feed?${queryParams.toString()}`);
  return { ...page, items: page.items.map(normalizeFeedItem) };
}

export async function rateFeedItem(
  soundcloudId: string | number,
  decisionOrRating: FeedDecision | FeedRating,
  options: RateFeedItemOptions = {}
): Promise<RateFeedItemResponse> {
  const decision =
    typeof decisionOrRating === 'number'
      ? feedRatingToDecision(decisionOrRating)
      : decisionOrRating;
  const body: Record<string, unknown> = { decision };
  if (options.surface) body.surface = options.surface;
  if (options.modelVersion) body.model_version = options.modelVersion;
  if (options.featureSnapshot) body.feature_snapshot = options.featureSnapshot;
  return getDefaultApiClient().post<RateFeedItemResponse>(
    `/feed/${encodeURIComponent(String(soundcloudId))}/rate`,
    body
  );
}

export async function materializeFeedItem(
  soundcloudId: string
): Promise<MaterializeFeedItemResponse> {
  return getDefaultApiClient().post<MaterializeFeedItemResponse>(
    `/feed/${encodeURIComponent(soundcloudId)}/materialize`
  );
}

/** One-time backfill retained for installations that have not completed it. */
export async function startFeedBackfill(): Promise<{ started: boolean }> {
  return getDefaultApiClient().post<{ started: boolean }>('/feed/backfill');
}
