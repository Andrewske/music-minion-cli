import { useState } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Music, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import {
  FEED_VERDICT_LABELS,
  REVIEWED_PAGE_SIZE,
  getReviewed,
  rateFeedItem,
  type FeedDecision,
  type FeedVerdict,
  type ReviewedItem,
} from '../../api/feed';
import type { PlayableFeedRow } from '../../hooks/usePlayFeedRow';
import { FlaggedList } from './FlaggedList';
import type { NoteTarget } from './NoteDialog';
import {
  REVIEWED_FILTERS,
  REVIEWED_QUERY_KEY,
  describeListen,
  formatDecidedAt,
  reviewedRateOptions,
  reviewedFilterLabel,
  type ReviewedFilter,
} from './reviewed';
import { VerdictButtons } from './VerdictButtons';

interface ReviewedRowProps {
  item: ReviewedItem;
  isUpdating: boolean;
  isPlaying: boolean;
  onPlay: (item: ReviewedItem) => void;
  onDecide: (item: ReviewedItem, verdict: FeedVerdict) => void;
  onEditNote: (target: NoteTarget) => void;
}

export function ReviewedRow({ item, isUpdating, isPlaying, onPlay, onDecide, onEditNote }: ReviewedRowProps): JSX.Element {
  const [artworkFailed, setArtworkFailed] = useState(false);
  const playable = item.access !== 'blocked';
  const editNote = (): void => onEditNote({ soundcloudId: item.soundcloud_id, title: item.title, note: item.note });
  return (
    <article
      aria-label={`${item.title ?? 'Untitled'} reviewed item`}
      className={`flex flex-wrap items-center gap-3 rounded border px-3 py-2 md:flex-nowrap ${
        isPlaying ? 'border-obsidian-accent/40 bg-obsidian-accent/10' : 'border-obsidian-border bg-obsidian-surface'
      }`}
    >
      <button type="button" onClick={() => playable && onPlay(item)} disabled={!playable} aria-label={`Play ${item.title ?? 'track'}`} className="shrink-0 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent disabled:opacity-40">
        {item.artwork_url && !artworkFailed ? (
          <img src={item.artwork_url} alt="" width={44} height={44} loading="lazy" onError={() => setArtworkFailed(true)} className="h-11 w-11 rounded object-cover" />
        ) : (
          <span className="flex h-11 w-11 items-center justify-center rounded bg-white/5"><Music className="h-4 w-4 text-white/40" /></span>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${isPlaying ? 'text-obsidian-accent' : 'text-white'}`}>{item.title ?? 'Untitled'}</p>
        <p className="truncate text-xs text-white/50">{item.artist_name ?? 'Unknown artist'}</p>
        <p className="mt-0.5 text-[11px] text-white/35">
          <span title={new Date(item.decided_at).toLocaleString()}>{FEED_VERDICT_LABELS[item.decision]} · {formatDecidedAt(item.decided_at)}</span>
          {' · '}
          <span>{describeListen(item)}</span>
        </p>
      </div>
      <button type="button" onClick={editNote} aria-label={item.note ? `Edit note: ${item.note}` : 'Add note'} className="flex min-h-10 max-w-xs items-center gap-1.5 rounded px-2 text-left text-xs text-white/50 hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent">
        <Pencil className="h-3.5 w-3.5 shrink-0" />
        <span className={`truncate ${item.note ? 'italic text-white/70' : ''}`}>{item.note ?? 'Add note'}</span>
      </button>
      <VerdictButtons current={item.decision} disabled={isUpdating} onDecide={(verdict) => onDecide(item, verdict)} />
    </article>
  );
}

interface ReviewedListProps {
  currentTrackId: number | null;
  onPlay: (item: PlayableFeedRow) => void;
  onEditNote: (target: NoteTarget) => void;
}

function FilterChips({ filter, onChange }: { filter: ReviewedFilter | undefined; onChange: (filter: ReviewedFilter | undefined) => void }): JSX.Element {
  return (
    <fieldset role="radiogroup" aria-label="Verdict filter" className="flex flex-wrap gap-1.5 pb-2">
      <legend className="sr-only">Verdict filter</legend>
      {REVIEWED_FILTERS.map((value) => (
        <button
          key={value ?? 'all'}
          type="button"
          role="radio"
          aria-checked={filter === value}
          onClick={() => onChange(value)}
          className={`rounded-full border px-3 py-1.5 text-xs ${filter === value ? 'border-obsidian-accent text-obsidian-accent' : 'border-obsidian-border text-white/60 hover:text-white'}`}
        >
          {reviewedFilterLabel(value)}
        </button>
      ))}
    </fieldset>
  );
}

/** Current decisions, newest first, with a verdict filter and inline changes. */
export function ReviewedList({ currentTrackId, onPlay, onEditNote }: ReviewedListProps): JSX.Element {
  const [filter, setFilter] = useState<ReviewedFilter | undefined>(undefined);
  return (
    <div className="flex-1 overflow-y-auto pb-4" aria-label="Reviewed tracks">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-2">
        <FilterChips filter={filter} onChange={setFilter} />
        {filter === 'flagged' ? (
          <FlaggedList source="user" currentTrackId={currentTrackId} emptyText="Nothing flagged as not for feed." onPlay={onPlay} />
        ) : (
          <DecisionList filter={filter} currentTrackId={currentTrackId} onPlay={onPlay} onEditNote={onEditNote} />
        )}
      </div>
    </div>
  );
}

function DecisionList({ filter, currentTrackId, onPlay, onEditNote }: ReviewedListProps & { filter: FeedDecision | undefined }): JSX.Element {
  const queryClient = useQueryClient();
  const reviewedQuery = useInfiniteQuery({
    queryKey: [...REVIEWED_QUERY_KEY, { filter }],
    queryFn: ({ pageParam }) => getReviewed({ decision: filter, cursor: pageParam, limit: REVIEWED_PAGE_SIZE }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
  const verdictMutation = useMutation({
    mutationFn: ({ item, verdict }: { item: ReviewedItem; verdict: FeedVerdict }) =>
      rateFeedItem(item.soundcloud_id, verdict, reviewedRateOptions(item.local_track_id)),
    onSuccess: (_response, { verdict }) => {
      toast.success(`Changed to ${FEED_VERDICT_LABELS[verdict]}`);
    },
    onError: () => toast.error('Verdict change failed'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: REVIEWED_QUERY_KEY }),
  });
  const items = reviewedQuery.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
    {reviewedQuery.isLoading ? (
      <div className="flex justify-center py-8 text-white/40" role="status" aria-label="Loading reviewed tracks"><Loader2 className="h-6 w-6 animate-spin" /></div>
    ) : reviewedQuery.isError ? (
      <p className="py-8 text-center text-sm text-white/50" role="alert">Failed to load reviewed tracks</p>
    ) : items.length === 0 ? (
      <p className="py-8 text-center text-sm text-white/40">Nothing reviewed with this verdict yet.</p>
    ) : (
      items.map((item) => (
        <ReviewedRow
          key={item.decision_id}
          item={item}
          isPlaying={item.local_track_id !== null && item.local_track_id === currentTrackId}
          isUpdating={verdictMutation.isPending && verdictMutation.variables?.item.soundcloud_id === item.soundcloud_id}
          onPlay={onPlay}
          onDecide={(target, verdict) => verdictMutation.mutate({ item: target, verdict })}
          onEditNote={onEditNote}
        />
      ))
    )}
    {reviewedQuery.hasNextPage && (
      <button type="button" onClick={() => void reviewedQuery.fetchNextPage()} disabled={reviewedQuery.isFetchingNextPage} className="mx-auto rounded border border-obsidian-border px-4 py-2 text-xs text-white/70 hover:text-white disabled:opacity-50">
        {reviewedQuery.isFetchingNextPage ? 'Loading…' : 'Load more'}
      </button>
    )}
    </>
  );
}
