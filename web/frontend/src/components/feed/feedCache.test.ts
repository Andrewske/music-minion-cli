import { QueryClient, type InfiniteData } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { FeedItem, FeedPage } from '../../api/feed';
import { invalidateFlagViews, removeFromAllFeeds, restoreFeeds } from './feedCache';
import { FLAGGED_QUERY_KEY } from './reviewed';

const page = (...ids: string[]): InfiniteData<FeedPage> => ({
  pages: [{ items: ids.map((id) => ({ soundcloud_id: id }) as FeedItem), next_cursor: null }],
  pageParams: [undefined],
});
const ids = (client: QueryClient, key: unknown[]): string[] =>
  client.getQueryData<InfiniteData<FeedPage>>(key)?.pages.flatMap((p) => p.items.map((i) => i.soundcloud_id)) ?? [];

describe('feed cache helpers', () => {
  it('removes a track from every feed variant and restores them all', async () => {
    const client = new QueryClient();
    const all = ['feed', { source: 'all' }];
    const reposts = ['feed', { source: 'reposts' }];
    client.setQueryData(all, page('1', '2'));
    client.setQueryData(reposts, page('2', '3'));
    client.setQueryData(FLAGGED_QUERY_KEY, 'untouched');

    const snapshot = await removeFromAllFeeds(client, '2');
    expect(ids(client, all)).toEqual(['1']);
    expect(ids(client, reposts)).toEqual(['3']);
    expect(client.getQueryData(FLAGGED_QUERY_KEY)).toBe('untouched');

    restoreFeeds(client, snapshot);
    expect(ids(client, all)).toEqual(['1', '2']);
    expect(ids(client, reposts)).toEqual(['2', '3']);
  });

  it('invalidates the flagged list, rule counts and artist stats', () => {
    const client = new QueryClient();
    const spy = vi.spyOn(client, 'invalidateQueries');
    invalidateFlagViews(client);
    const keys = spy.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toEqual([['feed-flagged'], ['feed-filter-rules'], ['artists']]);
  });
});
