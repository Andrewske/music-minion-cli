import { useCallback, useEffect, useMemo, useRef } from 'react';
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
import {
  FEED_PAGE_SIZE,
  FEED_RANK_PRESETS,
  applyFeedDecision,
  getFeed,
  hasPendingFeedSync,
  isFeedSyncFailed,
  materializeFeedItem,
  mergeFeedDecisionResponse,
  rateFeedItem,
  startFeedBackfill,
} from '../../api/feed';
import type {
  FeedDecision,
  FeedItem,
  FeedPage as FeedPageData,
  FeedRankPreset,
  FeedSource,
} from '../../api/feed';
import { syncFeed } from '../../api/artists';
import { useFeedSyncStatus } from '../../hooks/useArtists';
import { usePlayerStore } from '../../stores/playerStore';
import type { Track } from '@music-minion/shared';
import { FeedTrackCard } from './FeedTrackCard';

const ROW_HEIGHT = 92;
const routeApi = getRouteApi('/feed');

function toTrack(item: FeedItem, localTrackId = item.local_track_id): Track {
  const artist = item.uploader ?? item.artist ?? item.reposters[0];
  return {
    id: localTrackId as number,
    title: item.title ?? 'Untitled',
    artist: artist?.display_name ?? artist?.slug ?? 'Unknown artist',
    duration: item.duration_ms / 1000,
  };
}

function formatLastSync(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'never';
  const hours = Math.floor((Date.now() - date.getTime()) / 3_600_000);
  if (hours < 1) return '<1h ago';
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function FeedPage(): JSX.Element {
  const {
    source = 'all',
    maxRank,
    inLibrary = false,
    showHidden = false,
  } = routeApi.useSearch();
  const navigate = useNavigate({ from: '/feed' });
  const queryClient = useQueryClient();
  const play = usePlayerStore((state) => state.play);
  const currentTrackId = usePlayerStore((state) => state.currentTrack?.id ?? null);
  const parentRef = useRef<HTMLDivElement>(null);

  const feedQueryKey = ['feed', { source, maxRank, inLibrary, showHidden }] as const;
  const feedQuery = useInfiniteQuery({
    queryKey: feedQueryKey,
    queryFn: ({ pageParam }) =>
      getFeed({
        cursor: pageParam,
        limit: FEED_PAGE_SIZE,
        source,
        maxRank,
        inLibrary,
        showHidden,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    refetchInterval: (query) =>
      hasPendingFeedSync((query.state.data as InfiniteData<FeedPageData> | undefined)?.pages)
        ? 5_000
        : false,
  });

  const items = useMemo(
    () => feedQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [feedQuery.data]
  );
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 6,
  });
  const virtualItems = virtualizer.getVirtualItems();

  useEffect(() => {
    parentRef.current?.scrollTo({ top: 0 });
  }, [source, maxRank, inLibrary, showHidden]);

  useEffect(() => {
    const last = virtualItems[virtualItems.length - 1];
    if (
      last &&
      last.index >= items.length - 8 &&
      feedQuery.hasNextPage &&
      !feedQuery.isFetchingNextPage
    ) {
      void feedQuery.fetchNextPage();
    }
  }, [virtualItems, items.length, feedQuery]);

  const decisionMutation = useMutation({
    mutationFn: ({ item, decision }: { item: FeedItem; decision: FeedDecision }) =>
      rateFeedItem(item.soundcloud_id, decision, {
        surface: 'web',
        modelVersion: item.prediction_model_version ?? undefined,
      }),
    onMutate: async ({ item, decision }) => {
      await queryClient.cancelQueries({ queryKey: feedQueryKey });
      const previous = queryClient.getQueryData<InfiniteData<FeedPageData>>(feedQueryKey);
      queryClient.setQueryData<InfiniteData<FeedPageData>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items:
              decision !== 'keep' && !showHidden
                ? page.items.filter((candidate) => candidate.soundcloud_id !== item.soundcloud_id)
                : page.items.map((candidate) =>
                    candidate.soundcloud_id === item.soundcloud_id
                      ? applyFeedDecision(candidate, decision)
                      : candidate
                  ),
          })),
        };
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(feedQueryKey, context.previous);
      toast.error('Decision failed — your previous choice was restored');
    },
    onSuccess: (response, { item, decision }) => {
      queryClient.setQueryData<InfiniteData<FeedPageData>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items: page.items.map((candidate) =>
              candidate.soundcloud_id === item.soundcloud_id
                ? mergeFeedDecisionResponse(candidate, response)
                : candidate
            ),
          })),
        };
      });
      if (isFeedSyncFailed(response.action_state)) {
        toast.error('Kept locally; SoundCloud sync needs attention');
      } else if (decision === 'keep') {
        toast.success('Kept — SoundCloud sync queued');
      }
    },
  });

  const syncMutation = useMutation({
    mutationFn: syncFeed,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['feed'] });
      void queryClient.invalidateQueries({ queryKey: ['artists', 'feed-sync-status'] });
      toast.success('Feed synced');
    },
    onError: () => toast.error('Feed sync failed — check SoundCloud auth or try later'),
  });
  const backfillMutation = useMutation({
    mutationFn: startFeedBackfill,
    onSuccess: () => toast.success('Backfill started — sweeping followed artists'),
    onError: () => toast.error('Backfill failed to start — sync may be running'),
  });

  const { data: syncStatus } = useFeedSyncStatus();
  const backfillRunning =
    backfillMutation.isPending || syncStatus?.uploads_last_status === 'running';
  const previousUploadStatus = useRef<string | null>(null);
  useEffect(() => {
    const status = syncStatus?.uploads_last_status ?? null;
    if (previousUploadStatus.current === 'running' && status !== 'running') {
      void queryClient.invalidateQueries({ queryKey: ['feed'] });
    }
    previousUploadStatus.current = status;
  }, [syncStatus?.uploads_last_status, queryClient]);

  const handlePlay = useCallback(
    async (item: FeedItem): Promise<void> => {
      let localTrackId = item.local_track_id;
      if (localTrackId === null) {
        try {
          const materialized = await materializeFeedItem(item.soundcloud_id);
          localTrackId = materialized.local_track_id;
          queryClient.setQueriesData<InfiniteData<FeedPageData>>(
            { queryKey: ['feed'] },
            (old) => old && ({
              ...old,
              pages: old.pages.map((page) => ({
                ...page,
                items: page.items.map((candidate) =>
                  candidate.soundcloud_id === item.soundcloud_id
                    ? { ...candidate, local_track_id: materialized.local_track_id }
                    : candidate
                ),
              })),
            })
          );
        } catch {
          toast.error('Could not prepare this SoundCloud track for playback');
          return;
        }
      }
      const index = items.findIndex((candidate) => candidate.soundcloud_id === item.soundcloud_id);
      const followingIds = items
        .slice(Math.max(0, index))
        .map((candidate) =>
          candidate.soundcloud_id === item.soundcloud_id
            ? localTrackId
            : candidate.local_track_id
        )
        .filter((id): id is number => id !== null);
      void play(toTrack(item, localTrackId), {
        type: 'feed',
        track_ids: followingIds,
        shuffle: false,
      });
    },
    [items, play, queryClient]
  );

  const updateSearch = (patch: {
    source?: FeedSource;
    maxRank?: FeedRankPreset;
    inLibrary?: boolean;
    showHidden?: boolean;
  }): void => {
    void navigate({
      search: (previous: {
        source?: FeedSource;
        maxRank?: FeedRankPreset;
        inLibrary?: boolean;
        showHidden?: boolean;
      }) => ({ ...previous, ...patch }),
      replace: true,
    });
  };

  return (
    <div className="flex h-full flex-col px-3 pt-4 md:px-6">
      <header className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-3 pb-4">
        <h1 className="flex items-center gap-2 text-xl font-semibold text-white">
          <Rss className="h-5 w-5 text-obsidian-accent" /> Feed
        </h1>

        <fieldset role="radiogroup" className="flex items-center rounded-full border border-obsidian-border p-0.5" aria-label="Feed source">
          <legend className="sr-only">Feed source</legend>
          {(['all', 'releases', 'reposts'] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={source === value}
              onClick={() => updateSearch({ source: value === 'all' ? undefined : value })}
              className={`rounded-full px-3 py-1 text-xs capitalize focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent ${
                source === value ? 'bg-obsidian-accent/20 text-obsidian-accent' : 'text-white/60 hover:text-white'
              }`}
            >
              {value}
            </button>
          ))}
        </fieldset>

        <label className="flex items-center gap-2 text-xs text-white/60">
          Rank
          <select
            aria-label="Maximum artist rank"
            value={maxRank ?? ''}
            onChange={(event) =>
              updateSearch({
                maxRank: event.target.value
                  ? (Number(event.target.value) as FeedRankPreset)
                  : undefined,
              })
            }
            className="rounded border border-obsidian-border bg-obsidian-surface px-2 py-1.5 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent"
          >
            <option value="">All</option>
            {FEED_RANK_PRESETS.map((rank) => <option key={rank} value={rank}>Top {rank}</option>)}
          </select>
        </label>

        <button type="button" aria-pressed={inLibrary} onClick={() => updateSearch({ inLibrary: inLibrary ? undefined : true })} className={`rounded-full border px-3 py-1.5 text-xs ${inLibrary ? 'border-obsidian-accent text-obsidian-accent' : 'border-obsidian-border text-white/60'}`}>
          In library
        </button>
        <button type="button" aria-pressed={showHidden} onClick={() => updateSearch({ showHidden: showHidden ? undefined : true })} className={`rounded-full border px-3 py-1.5 text-xs ${showHidden ? 'border-obsidian-accent text-obsidian-accent' : 'border-obsidian-border text-white/60'}`}>
          Show hidden
        </button>

        <div className="ml-auto flex items-center gap-1 text-xs text-white/40">
          <span>Synced {formatLastSync(syncStatus?.uploads_last_run_at ?? syncStatus?.last_run_at)}</span>
          <button type="button" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending} aria-label="Sync feed now" className="rounded p-2 text-white/60 hover:bg-white/5 hover:text-white disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent">
            <RefreshCw className={`h-4 w-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {feedQuery.isLoading ? (
        <div className="flex flex-1 items-center justify-center text-white/40" role="status" aria-label="Loading feed"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : feedQuery.isError ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-white/50" role="alert">
          <span>Failed to load feed</span>
          <button type="button" onClick={() => void feedQuery.refetch()} className="rounded border border-obsidian-border px-3 py-1.5 text-white/70">Try again</button>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-white/40">
          <p>No tracks for these filters.</p>
          {backfillRunning ? (
            <p className="flex items-center gap-2" role="status"><Loader2 className="h-4 w-4 animate-spin" />Backfill running</p>
          ) : (
            <button type="button" onClick={() => backfillMutation.mutate()} className="rounded border border-obsidian-accent px-4 py-2 text-obsidian-accent hover:bg-obsidian-accent/10">Backfill feed history</button>
          )}
        </div>
      ) : (
        <div ref={parentRef} className="flex-1 overflow-y-auto pb-4" aria-label="SoundCloud feed">
          <div className="relative mx-auto w-full max-w-5xl" style={{ height: virtualizer.getTotalSize() }}>
            {virtualItems.map((virtualRow) => {
              const item = items[virtualRow.index];
              return (
                <div
                  key={item.soundcloud_id}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  className="absolute left-0 top-0 w-full px-0.5 pb-2"
                  style={{ transform: `translateY(${virtualRow.start}px)` }}
                >
                  <FeedTrackCard
                    item={item}
                    isPlaying={item.local_track_id !== null && item.local_track_id === currentTrackId}
                    isUpdating={decisionMutation.isPending && decisionMutation.variables?.item.soundcloud_id === item.soundcloud_id}
                    onPlay={(target) => void handlePlay(target)}
                    onDecide={(target, decision) => decisionMutation.mutate({ item: target, decision })}
                  />
                </div>
              );
            })}
          </div>
          {feedQuery.isFetchingNextPage && <div className="flex justify-center py-3 text-white/40" role="status" aria-label="Loading more tracks"><Loader2 className="h-5 w-5 animate-spin" /></div>}
        </div>
      )}
    </div>
  );
}
