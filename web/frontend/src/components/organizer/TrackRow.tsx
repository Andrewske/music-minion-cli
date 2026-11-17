import { forwardRef } from 'react';
import type { CSSProperties, HTMLAttributes, KeyboardEvent } from 'react';
import { GripVertical } from 'lucide-react';
import type { PlaylistTrackEntry } from '../../types';
import { formatFullDate, formatRelativeDate } from './trackDate';

/** Row height for virtualized lists: compact table row on desktop, stacked card on mobile. */
export const TRACK_ROW_HEIGHT = { desktop: 40, mobile: 56 } as const;

function formatNumber(val: number | undefined): string | number {
  return val ? Math.round(val) : '-';
}

// Shared column layout so the header, unassigned rows and bucket rows line up.
const COL = {
  grip: 'flex-none w-10 px-3',
  title: 'flex-3 min-w-0 px-3',
  artist: 'hidden md:flex flex-2 min-w-0 px-3 items-center gap-1.5',
  bpm: 'hidden md:block flex-none w-[50px] px-3',
  key: 'hidden md:block flex-none w-[60px] px-3',
  rating: 'hidden md:block flex-none w-[70px] px-3',
  date: 'hidden md:block flex-none w-[50px] px-3',
} as const;

function Reposters({ track }: { track: PlaylistTrackEntry }): JSX.Element | null {
  const reposters = track.reposters;
  if (!reposters || reposters.length === 0) return null;
  return (
    <div className="flex -space-x-1.5 shrink-0">
      {reposters.slice(0, 4).map((r) => (
        <img
          key={r.slug}
          src={r.avatar_url?.replace('-large', '-small') ?? ''}
          alt={r.name}
          title={r.name}
          className="w-4 h-4 rounded-full ring-1 ring-black"
        />
      ))}
      {reposters.length > 4 && (
        <span className="text-[10px] text-white/30 pl-1">+{reposters.length - 4}</span>
      )}
    </div>
  );
}

export function TrackRowHeader(): JSX.Element {
  return (
    <div className="hidden md:flex items-center py-2 border-b border-obsidian-border bg-obsidian-surface text-xs tracking-wider uppercase text-white/30">
      <div className={COL.grip} />
      <div className={COL.title}>Title</div>
      <div className={COL.artist}>Artist</div>
      <div className={COL.bpm}>BPM</div>
      <div className={COL.key}>Key</div>
      <div className={COL.rating}>Rating</div>
      <div className={COL.date}>Date</div>
    </div>
  );
}

function TrackMetaCells({ track }: { track: PlaylistTrackEntry }): JSX.Element {
  return (
    <>
      <div className={`${COL.artist} text-white/50`}>
        <span className="truncate" title={track.artist ?? ''}>{track.artist ?? '-'}</span>
        <Reposters track={track} />
      </div>
      <div className={`${COL.bpm} text-white/50`}>{formatNumber(track.bpm)}</div>
      <div className={`${COL.key} text-white/50 truncate`}>{track.key_signature ?? '-'}</div>
      <div className={`${COL.rating} text-white/50`}>{formatNumber(track.rating)}</div>
      <div className={`${COL.date} text-white/50`} title={formatFullDate(track.added_at)}>
        {formatRelativeDate(track.added_at)}
      </div>
    </>
  );
}

function TitleCell({ track, isPlaying }: { track: PlaylistTrackEntry; isPlaying: boolean }): JSX.Element {
  return (
    <div className={COL.title}>
      <div className={`truncate ${isPlaying ? 'text-obsidian-accent font-medium' : 'text-white/90 md:text-white/50'}`} title={track.title}>
        {track.title ?? '-'}
      </div>
      <div className="md:hidden text-xs text-white/50 truncate">{track.artist ?? 'Unknown Artist'}</div>
    </div>
  );
}

interface TrackRowProps extends HTMLAttributes<HTMLDivElement> {
  track: PlaylistTrackEntry;
  isPlaying?: boolean;
  /** Click or Enter. Space stays with dnd-kit's keyboard drag. */
  onPlay?: () => void;
  style?: CSSProperties;
}

const ROW_CLASS = 'relative flex items-center h-14 md:h-10 text-sm border-b border-obsidian-border/50 cursor-pointer touch-manipulation select-none [-webkit-touch-callout:none] transition-colors';

/**
 * One track in the organizer: unassigned list, bucket list and drag preview all
 * render this. Callers spread dnd-kit `attributes`/`listeners` onto it so the
 * whole row is the drag handle; a click without movement still plays.
 * Height matches TRACK_ROW_HEIGHT.
 */
export const TrackRow = forwardRef<HTMLDivElement, TrackRowProps>(function TrackRow(
  { track, isPlaying = false, onPlay, onKeyDown, className = '', ...rest },
  ref,
): JSX.Element {
  const unavailable = track.available === false;
  const tone = isPlaying
    ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent'
    : 'bg-obsidian-surface hover:bg-white/5';
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === 'Enter' && onPlay) {
      e.preventDefault();
      onPlay();
      return;
    }
    onKeyDown?.(e);
  };

  return (
    <div
      ref={ref}
      {...rest}
      onClick={onPlay}
      onKeyDown={handleKeyDown}
      className={`${ROW_CLASS} ${tone} ${unavailable ? 'opacity-50' : ''} ${className}`}
    >
      <div className={`${COL.grip} text-white/30`}>
        <GripVertical className="w-4 h-4" />
      </div>
      <TitleCell track={track} isPlaying={isPlaying} />
      <TrackMetaCells track={track} />
      {unavailable && (
        <span className="absolute right-2 top-1/2 -translate-y-1/2 z-10 text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-sm bg-red-500/15 text-red-400 border border-red-500/30">
          Unavailable
        </span>
      )}
    </div>
  );
});
