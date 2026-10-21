import type { InfiniteData, QueryClient } from '@tanstack/react-query';
import type { FeedDecision, RateFeedItemOptions, ReviewedItem, ReviewedPage } from '../../api/feed';
import { formatListenTime } from '../../lib/feedListen';
import { getPlayedListenStats } from '../../stores/listenStore';

export const REVIEWED_QUERY_KEY = ['feed-reviewed'] as const;
export const REVIEWED_FILTERS: ReadonlyArray<FeedDecision | undefined> = [
  undefined,
  'keep',
  'not_quite',
  'nope',
];

export function formatDecidedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** "0:42 played · reached 1:30": time played, then furthest position. */
export function describeListen(item: Pick<ReviewedItem, 'listen_seconds' | 'max_position_ms'>): string {
  if (item.listen_seconds === null) return 'Not tracked';
  const reached =
    item.max_position_ms === null ? '' : ` · reached ${formatListenTime(item.max_position_ms / 1000)}`;
  return `${formatListenTime(item.listen_seconds)} played${reached}`;
}

/**
 * A re-rate sends listen stats only when the track was replayed this
 * session; otherwise the backend carries the previous verdict's stats forward.
 */
export function reviewedRateOptions(localTrackId: number | null): RateFeedItemOptions {
  const listen = getPlayedListenStats(localTrackId);
  return listen
    ? { surface: 'web_reviewed', listenSeconds: listen.listenSeconds, maxPositionMs: listen.maxPositionMs }
    : { surface: 'web_reviewed' };
}

/** The cached Reviewed pages with one soundcloud row pointed at its new local track. */
export function withMaterializedId(
  data: InfiniteData<ReviewedPage> | undefined,
  soundcloudId: string,
  localTrackId: number,
): InfiniteData<ReviewedPage> | undefined {
  if (!data) return data;
  const pages = data.pages.map((page) => ({
    ...page,
    items: page.items.map((row) =>
      row.soundcloud_id === soundcloudId ? { ...row, local_track_id: localTrackId } : row,
    ),
  }));
  return { ...data, pages };
}

/**
 * Playing a Reviewed row with no local track creates one. Every cached
 * Reviewed variant learns its id, so a re-rate finds this session's listen tally.
 */
export function cacheMaterializedReviewed(
  queryClient: QueryClient,
  soundcloudId: string,
  localTrackId: number,
): void {
  queryClient.setQueriesData<InfiniteData<ReviewedPage>>({ queryKey: REVIEWED_QUERY_KEY }, (old) =>
    withMaterializedId(old, soundcloudId, localTrackId),
  );
}
