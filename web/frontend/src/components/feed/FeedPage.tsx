import { useCallback, useEffect, useRef } from 'react';
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { getRouteApi, useNavigate } from '@tanstack/react-router';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Loader2, RefreshCw, Rss } from 'lucide-react';
import { toast } from 'sonner';
import { getFeed, rateFeedItem, startFeedBackfill } from '../../api/feed';
import type { FeedItem, FeedPage as FeedPageData, FeedRating } from '../../api/feed';
import { syncFeed } from '../../api/artists';
import { useFeedSyncStatus } from '../../hooks/useArtists';
import { usePlayerStore } from '../../stores/playerStore';
import type { Track } from '@music-minion/shared';
import { FeedTrackCard } from './FeedTrackCard';

const PAGE_SIZE = 30;
const ROW_HEIGHT = 76;

const routeApi = getRouteApi('/feed');

function toTrack(item: FeedItem): Track {
  return {
    id: item.local_track_id as number,
    title: item.title ?? 'Untitled',
    artist: item.artist.display_name ?? item.artist.slug,
    duration: item.duration_ms / 1000,
  };
}

function formatLastSync(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return 'never';
  const hours = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60));
  if (hours < 1) return '<1h ago';
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function FeedPage(): JSX.Element {
  const { top200 = false, inLibrary = false } = routeApi.useSearch();
  const navigate = useNavigate({ from: '/feed' });
  const queryClient = useQueryClient();
  const play = usePlayerStore((s) => s.play);
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id ?? null);
  const parentRef = useRef<HTMLDivElement>(null);

  const feedQueryKey = ['feed', { top200, inLibrary }] as const;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
  } = useInfiniteQuery({
    queryKey: feedQueryKey,
    queryFn: ({ pageParam }) =>
      getFeed({ cursor: pageParam, limit: PAGE_SIZE, top200, inLibrary }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
  });

  // Fetch the next page when the last rendered row comes into range.
  const virtualItems = virtualizer.getVirtualItems();
  useEffect(() => {
    const last = virtualItems[virtualItems.length - 1];
    if (!last) return;
    if (last.index >= items.length - 5 && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [virtualItems, items.length, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const rateMutation = useMutation({
    mutationFn: ({ item, value }: { item: FeedItem; value: FeedRating }) =>
      rateFeedItem(item.id, value),
    onMutate: async ({ item, value }) => {
      await queryClient.cancelQueries({ queryKey: feedQueryKey });
      const previous =
        queryClient.getQueryData<InfiniteData<FeedPageData>>(feedQueryKey);
      queryClient.setQueryData<InfiniteData<FeedPageData>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items:
              value === 1
                ? page.items.map((i) =>
                    i.id === item.id ? { ...i, status: 'liked' as const } : i
                  )
                : page.items.filter((i) => i.id !== item.id),
          })),
        };
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(feedQueryKey, context.previous);
      }
      toast.error('Rating failed');
    },
    onSuccess: (_data, { value }) => {
      if (value === 1) toast.success('Liked — adding to monthly playlist');
    },
  });

  const syncMutation = useMutation({
    mutationFn: syncFeed,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['artists', 'feed-sync-status'] });
      toast.success('Feed synced');
    },
    onError: () => toast.error('Feed sync failed — check SC auth or try later'),
  });

  const backfillMutation = useMutation({
    mutationFn: startFeedBackfill,
    onSuccess: () =>
      toast.success('Backfill started — sweeping all followed artists (~20 min)'),
    onError: () => toast.error('Backfill failed to start — sync may be running'),
  });

  const { data: syncStatus } = useFeedSyncStatus();
  const backfillRunning =
    backfillMutation.isPending || syncStatus?.uploads_last_status === 'running';

  // When a running backfill finishes (status polls every 30s), pull in results.
  const prevUploadStatus = useRef<string | null>(null);
  useEffect(() => {
    const status = syncStatus?.uploads_last_status ?? null;
    if (prevUploadStatus.current === 'running' && status !== 'running') {
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    }
    prevUploadStatus.current = status;
  }, [syncStatus?.uploads_last_status, queryClient]);

  const handlePlay = useCallback(
    (item: FeedItem): void => {
      const index = items.findIndex((i) => i.id === item.id);
      if (index === -1 || item.local_track_id === null) return;
      // Sequential from the clicked row, shuffle forced off. Slicing here
      // (instead of start_index) sidesteps the backend queue-window pitfall.
      const trackIds = items
        .slice(index)
        .filter((i) => i.local_track_id !== null)
        .map((i) => i.local_track_id as number);
      play(toTrack(item), { type: 'feed', track_ids: trackIds, shuffle: false });
    },
    [items, play]
  );

  const toggleFilter = (key: 'top200' | 'inLibrary'): void => {
    navigate({
      search: (prev: { top200?: boolean; inLibrary?: boolean }) => ({
        ...prev,
        [key]: prev[key] ? undefined : true,
      }),
    });
  };

  return (
    <div className="h-full flex flex-col px-4 md:px-6 pt-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 pb-4">
        <h1 className="text-xl font-semibold text-white flex items-center gap-2">
          <Rss className="w-5 h-5 text-obsidian-accent" />
          Feed
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => toggleFilter('top200')}
            className={`px-3 py-1 rounded-full text-xs border transition-colors ${
              top200
                ? 'bg-obsidian-accent/15 border-obsidian-accent text-obsidian-accent'
                : 'border-obsidian-border text-white/60 hover:text-white'
            }`}
          >
            Top 200
          </button>
          <button
            onClick={() => toggleFilter('inLibrary')}
            className={`px-3 py-1 rounded-full text-xs border transition-colors ${
              inLibrary
                ? 'bg-obsidian-accent/15 border-obsidian-accent text-obsidian-accent'
                : 'border-obsidian-border text-white/60 hover:text-white'
            }`}
          >
            In library
          </button>
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs text-white/40">
          <span>Synced {formatLastSync(syncStatus?.uploads_last_run_at ?? syncStatus?.last_run_at)}</span>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            aria-label="Sync feed now"
            className="p-2 rounded text-white/60 hover:text-white hover:bg-white/5 disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`}
            />
          </button>
        </div>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center text-white/40">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : isError ? (
        <div className="flex-1 flex items-center justify-center text-white/40 text-sm">
          Failed to load feed
        </div>
      ) : items.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-white/40 text-sm">
          <p>No uploads yet{top200 || inLibrary ? ' for these filters' : ''}.</p>
          {backfillRunning ? (
            <p className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Backfill running — sweeping followed artists, check back in a few minutes
            </p>
          ) : (
            <button
              onClick={() => backfillMutation.mutate()}
              className="px-4 py-2 rounded border border-obsidian-accent text-obsidian-accent hover:bg-obsidian-accent/10 transition-colors"
            >
              Backfill uploads since Jan 2026
            </button>
          )}
        </div>
      ) : (
        <div ref={parentRef} className="flex-1 overflow-y-auto pb-4">
          <div
            className="relative w-full"
            style={{ height: virtualizer.getTotalSize() }}
          >
            {virtualItems.map((virtualRow) => {
              const item = items[virtualRow.index];
              return (
                <div
                  key={item.id}
                  className="absolute left-0 w-full px-0.5"
                  style={{
                    top: 0,
                    transform: `translateY(${virtualRow.start}px)`,
                    height: ROW_HEIGHT,
                  }}
                >
                  <FeedTrackCard
                    item={item}
                    isPlaying={
                      item.local_track_id !== null &&
                      item.local_track_id === currentTrackId
                    }
                    onPlay={handlePlay}
                    onRate={(target, value) =>
                      rateMutation.mutate({ item: target, value })
                    }
                  />
                </div>
              );
            })}
          </div>
          {isFetchingNextPage && (
            <div className="flex justify-center py-3 text-white/40">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
