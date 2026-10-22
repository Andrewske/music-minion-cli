import { useState } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Music } from 'lucide-react';
import { toast } from 'sonner';
import {
  FLAGGED_PAGE_SIZE,
  getFlaggedTracks,
  unflagFeedItem,
  type FlaggedItem,
  type FlaggedSort,
  type FlaggedSourceFilter,
} from '../../api/feedFilters';
import { describeFlag, formatFlagDuration } from './flagged';
import { FILTER_RULES_QUERY_KEY, FLAGGED_QUERY_KEY, formatDecidedAt } from './reviewed';

interface FlaggedRowProps {
  item: FlaggedItem;
  isPlaying: boolean;
  isUpdating: boolean;
  onPlay: (item: FlaggedItem) => void;
  onUnflag: (item: FlaggedItem) => void;
}

export function FlaggedRow({ item, isPlaying, isUpdating, onPlay, onUnflag }: FlaggedRowProps): JSX.Element {
  const [artworkFailed, setArtworkFailed] = useState(false);
  const playable = item.access !== 'blocked';
  const action = item.source === 'user' ? 'Un-flag' : 'Rescue';
  return (
    <article
      aria-label={`${item.title ?? 'Untitled'} flagged item`}
      className={`flex flex-wrap items-center gap-3 rounded border px-3 py-2 md:flex-nowrap ${
        isPlaying ? 'border-obsidian-accent/40 bg-obsidian-accent/10' : 'border-obsidian-border bg-obsidian-surface'
      }`}
    >
      <button type="button" onClick={() => playable && onPlay(item)} disabled={!playable} aria-label={`Play ${item.title ?? 'track'}`} className="shrink-0 rounded-sm focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-obsidian-accent disabled:opacity-40">
        {item.artwork_url && !artworkFailed ? (
          <img src={item.artwork_url} alt="" width={44} height={44} loading="lazy" onError={() => setArtworkFailed(true)} className="h-11 w-11 rounded-sm object-cover" />
        ) : (
          <span className="flex h-11 w-11 items-center justify-center rounded-sm bg-white/5"><Music className="h-4 w-4 text-white/40" /></span>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${isPlaying ? 'text-obsidian-accent' : 'text-white'}`}>{item.title ?? 'Untitled'}</p>
        <p className="truncate text-xs text-white/50">{item.artist_name ?? 'Unknown artist'}</p>
        <p className="mt-0.5 truncate text-[11px] text-white/35">
          {describeFlag(item)} · {formatDecidedAt(item.created_at)}
          {item.note && <span className="italic text-white/55"> · {item.note}</span>}
        </p>
      </div>
      <span className="shrink-0 font-sf-mono text-xs text-white/40">{formatFlagDuration(item.duration_ms)}</span>
      <button
        type="button"
        onClick={() => onUnflag(item)}
        disabled={isUpdating}
        aria-label={`${action} ${item.title ?? 'track'}`}
        className="min-h-10 shrink-0 rounded-sm border border-obsidian-border px-3 text-xs text-white/70 hover:border-obsidian-accent hover:text-obsidian-accent disabled:opacity-50"
      >
        {action}
      </button>
    </article>
  );
}

interface FlaggedListProps {
  source: FlaggedSourceFilter;
  ruleId?: number;
  sort?: FlaggedSort;
  currentTrackId: number | null;
  emptyText: string;
  onPlay: (item: FlaggedItem) => void;
}

interface FlaggedCursor {
  cursor: number;
  cursorConfidence: number | null;
}

/** Active flags, newest or lowest agent confidence first; un-flag / rescue returns the track to the feed. */
export function FlaggedList({ source, ruleId, sort = 'newest', currentTrackId, emptyText, onPlay }: FlaggedListProps): JSX.Element {
  const queryClient = useQueryClient();
  const flaggedQuery = useInfiniteQuery({
    queryKey: [...FLAGGED_QUERY_KEY, { source, ruleId, sort }],
    queryFn: ({ pageParam }) =>
      getFlaggedTracks({ source, ruleId, sort, limit: FLAGGED_PAGE_SIZE, cursor: pageParam?.cursor, cursorConfidence: pageParam?.cursorConfidence }),
    initialPageParam: undefined as FlaggedCursor | undefined,
    getNextPageParam: (lastPage): FlaggedCursor | undefined =>
      lastPage.next_cursor === null ? undefined : { cursor: lastPage.next_cursor, cursorConfidence: lastPage.next_cursor_confidence },
  });
  const unflagMutation = useMutation({
    mutationFn: (item: FlaggedItem) => unflagFeedItem(item.soundcloud_id),
    onSuccess: (response) => toast.success(response.removed ? 'Un-flagged, back in the feed' : 'Rescued, back in the feed'),
    onError: () => toast.error('Could not return the track to the feed'),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: FLAGGED_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ['feed'] });
      void queryClient.invalidateQueries({ queryKey: FILTER_RULES_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ['artists'] });
    },
  });
  const items = flaggedQuery.data?.pages.flatMap((page) => page.items) ?? [];

  if (flaggedQuery.isLoading) {
    return <div className="flex justify-center py-8 text-white/40" role="status" aria-label="Loading flagged tracks"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }
  if (flaggedQuery.isError) {
    return <p className="py-8 text-center text-sm text-white/50" role="alert">Failed to load flagged tracks</p>;
  }
  if (items.length === 0) return <p className="py-8 text-center text-sm text-white/40">{emptyText}</p>;
  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <FlaggedRow
          key={item.flag_id}
          item={item}
          isPlaying={item.local_track_id !== null && item.local_track_id === currentTrackId}
          isUpdating={unflagMutation.isPending && unflagMutation.variables?.flag_id === item.flag_id}
          onPlay={onPlay}
          onUnflag={(target) => unflagMutation.mutate(target)}
        />
      ))}
      {flaggedQuery.hasNextPage && (
        <button type="button" onClick={() => void flaggedQuery.fetchNextPage()} disabled={flaggedQuery.isFetchingNextPage} className="mx-auto rounded-sm border border-obsidian-border px-4 py-2 text-xs text-white/70 hover:text-white disabled:opacity-50">
          {flaggedQuery.isFetchingNextPage ? 'Loading…' : 'Load more'}
        </button>
      )}
    </div>
  );
}
