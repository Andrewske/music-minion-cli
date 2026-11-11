import { Repeat2, Upload } from 'lucide-react';
import { getScLikeState } from '../../api/feed';
import type { StoriesTrack } from '../../api/stories';
import { KeepScoreBadge } from '../KeepScoreBadge';
import { ScLikeHeart } from '../ScLikeHeart';
import { STORIES_VERDICT_LABELS, formatDuration } from './storiesFormat';

const VERDICT_TONES = {
  keep: 'bg-obsidian-accent/15 text-obsidian-accent',
  not_quite: 'bg-white/10 text-white/70',
  nope: 'bg-red-400/10 text-red-300',
} as const;

interface TrackRowProps {
  track: StoriesTrack;
  index: number;
  isCurrent: boolean;
  onPlay: (track: StoriesTrack) => void;
}

function TrackRow({ track, index, isCurrent, onPlay }: TrackRowProps): JSX.Element {
  const KindIcon = track.kind === 'repost' ? Repeat2 : Upload;
  return (
    <li>
      <button
        type="button"
        onClick={() => onPlay(track)}
        aria-current={isCurrent ? 'true' : undefined}
        aria-label={`${track.title ?? 'Untitled'}${track.listened ? ' (heard)' : ''}`}
        data-listened={track.listened ? 'true' : 'false'}
        className={`flex w-full items-center gap-3 rounded px-3 py-2 text-left transition-colors focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-obsidian-accent ${
          isCurrent ? 'bg-obsidian-accent/10 ring-1 ring-obsidian-accent/40' : 'hover:bg-white/5'
        } ${track.listened && !isCurrent ? 'opacity-45 hover:opacity-80' : ''}`}
      >
        <span className="w-5 shrink-0 text-right font-sf-mono text-xs text-white/35">{index + 1}</span>
        <span className="min-w-0 flex-1">
          <span className={`block truncate text-sm ${isCurrent ? 'text-obsidian-accent' : 'text-white'}`}>{track.title ?? 'Untitled'}</span>
          <span className="flex items-center gap-1 truncate text-xs text-white/45">
            <KindIcon className="h-3 w-3 shrink-0" aria-label={track.kind} />
            <span className="truncate">{track.artist_name ?? 'Unknown artist'}</span>
          </span>
        </span>
        <KeepScoreBadge probability={track.score} />
        <ScLikeHeart state={getScLikeState(track.sc_liked, track.sc_like_action)} className="h-3.5 w-3.5" />
        {track.decision && (
          <span className={`shrink-0 rounded-sm px-1.5 py-0.5 text-[10px] ${VERDICT_TONES[track.decision]}`}>
            {STORIES_VERDICT_LABELS[track.decision]}
          </span>
        )}
        <span className="shrink-0 font-sf-mono text-xs text-white/40">{formatDuration(track.duration_ms)}</span>
      </button>
    </li>
  );
}

interface StoriesTrackListProps {
  tracks: readonly StoriesTrack[];
  currentId: string | null;
  onPlay: (track: StoriesTrack) => void;
}

/** Every track this artist posted in the window; heard ones dimmed but still playable. */
export function StoriesTrackList({ tracks, currentId, onPlay }: StoriesTrackListProps): JSX.Element {
  return (
    <ol aria-label="Artist tracks" className="flex flex-col gap-0.5">
      {tracks.map((track, index) => (
        <TrackRow key={track.soundcloud_id} track={track} index={index} isCurrent={track.soundcloud_id === currentId} onPlay={onPlay} />
      ))}
    </ol>
  );
}
