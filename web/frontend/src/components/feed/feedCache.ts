import type { InfiniteData, QueryClient, QueryKey } from '@tanstack/react-query';
import type { FeedPage } from '../../api/feed';
import { FLAGGED_QUERY_KEY, FILTER_RULES_QUERY_KEY } from './reviewed';

/** Every feed list variant (source/rank/sort/score filters) shares this prefix. */
export const FEED_QUERY_PREFIX = ['feed'] as const;

export type FeedSnapshot = ReadonlyArray<[QueryKey, InfiniteData<FeedPage> | undefined]>;

function withoutItem(data: InfiniteData<FeedPage> | undefined, soundcloudId: string): InfiniteData<FeedPage> | undefined {
  return data && {
    ...data,
    pages: data.pages.map((page) => ({
      ...page,
      items: page.items.filter((item) => item.soundcloud_id !== soundcloudId),
    })),
  };
}

/**
 * Optimistically drop a track from every cached feed variant, not just the
 * one on screen, so switching filters never shows a track already handled.
 * Returns a snapshot for restoreFeeds on failure.
 */
export async function removeFromAllFeeds(queryClient: QueryClient, soundcloudId: string): Promise<FeedSnapshot> {
  await queryClient.cancelQueries({ queryKey: FEED_QUERY_PREFIX });
  const snapshot = queryClient.getQueriesData<InfiniteData<FeedPage>>({ queryKey: FEED_QUERY_PREFIX });
  queryClient.setQueriesData<InfiniteData<FeedPage>>({ queryKey: FEED_QUERY_PREFIX }, (old) =>
    withoutItem(old, soundcloudId)
  );
  return snapshot;
}

export function restoreFeeds(queryClient: QueryClient, snapshot: FeedSnapshot): void {
  snapshot.forEach(([key, data]) => queryClient.setQueryData(key, data));
}

/**
 * After any flag change: flagged lists, rule hit counts and artist stats all
 * moved. The feed itself is refetched by the caller once no feed mutation is
 * still in flight.
 */
export function invalidateFlagViews(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: FLAGGED_QUERY_KEY });
  void queryClient.invalidateQueries({ queryKey: FILTER_RULES_QUERY_KEY });
  void queryClient.invalidateQueries({ queryKey: ['artists'] });
}
