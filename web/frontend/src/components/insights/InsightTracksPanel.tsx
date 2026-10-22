import { useQuery } from '@tanstack/react-query';
import { Loader2, Play, X } from 'lucide-react';
import { FEED_VERDICT_LABELS } from '../../api/feed';
import { INSIGHT_DIMENSION_LABELS, getInsightTracks, type InsightDimension, type InsightTrack } from '../../api/insights';
import { usePlayFeedRow } from '../../hooks/usePlayFeedRow';
import { formatFlagDuration } from '../feed/flagged';
import { formatDecidedAt } from '../feed/reviewed';
import { INSIGHTS_QUERY_KEY } from './insightsView';

const VERDICT_TONE: Record<InsightTrack['decision'], string> = {
  keep: 'text-obsidian-accent',
  not_quite: 'text-amber-300',
  nope: 'text-red-400',
};

export function InsightTrackRow({ track, onPlay }: { track: InsightTrack; onPlay: (track: InsightTrack) => void }): JSX.Element {
  const title = track.title ?? 'Untitled';
  return (
    <li className="flex items-center gap-3 border-t border-obsidian-border py-2">
      <button type="button" onClick={() => onPlay(track)} disabled={track.access === 'blocked'} aria-label={`Play ${title}`} className="shrink-0 rounded-sm p-1.5 text-white/50 hover:bg-white/10 hover:text-white disabled:opacity-40">
        <Play className="h-3.5 w-3.5" />
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-white">{title}</p>
        <p className="truncate text-xs text-white/50">
          {track.uploader ?? 'Unknown artist'} · {formatFlagDuration(track.duration_ms)}
          {track.note && <span className="italic text-white/60"> · {track.note}</span>}
        </p>
      </div>
      <span className={`shrink-0 text-xs ${VERDICT_TONE[track.decision]}`}>{FEED_VERDICT_LABELS[track.decision]}</span>
      <span className="hidden w-14 shrink-0 text-right text-[11px] text-white/35 sm:block">{formatDecidedAt(track.decided_at)}</span>
    </li>
  );
}

interface InsightTracksPanelProps {
  dimension: InsightDimension;
  value: string;
  onClose: () => void;
}

/** The reviewed tracks behind one Insights row. */
export function InsightTracksPanel({ dimension, value, onClose }: InsightTracksPanelProps): JSX.Element {
  const tracksQuery = useQuery({
    queryKey: [...INSIGHTS_QUERY_KEY, 'tracks', dimension, value],
    queryFn: () => getInsightTracks(dimension, value),
  });
  const playRow = usePlayFeedRow();
  const play = (track: InsightTrack): void => void playRow({ ...track, artist_name: track.uploader });
  const data = tracksQuery.data;
  return (
    <section aria-label={`Tracks for ${value}`} className="rounded-sm border border-obsidian-border bg-obsidian-surface p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-white/40">{INSIGHT_DIMENSION_LABELS[dimension]}</p>
          <h3 className="text-base font-semibold text-white">{value}</h3>
          {data && <p className="text-xs text-white/50">{data.total} reviewed track{data.total === 1 ? '' : 's'}{data.total > data.items.length ? `, newest ${data.items.length} shown` : ''}</p>}
        </div>
        <button type="button" onClick={onClose} aria-label="Close track list" className="rounded-sm p-1.5 text-white/50 hover:bg-white/10 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>
      {tracksQuery.isLoading && <div className="flex justify-center py-6 text-white/40" role="status" aria-label="Loading tracks"><Loader2 className="h-5 w-5 animate-spin" /></div>}
      {tracksQuery.isError && <p className="py-4 text-sm text-white/50" role="alert">Failed to load tracks</p>}
      {data && (
        <ul className="mt-2 max-h-[60vh] overflow-y-auto">
          {data.items.map((track) => <InsightTrackRow key={track.soundcloud_id} track={track} onPlay={play} />)}
        </ul>
      )}
    </section>
  );
}
