import { useState } from 'react';
import { MoreHorizontal, SkipForward, Trash2 } from 'lucide-react';
import type { TrackInfo } from '../../types';
import { WaveformPlayer } from '../WaveformPlayer';
import { Backdrop, TrackBannerInfo } from '../organizer/TrackBannerParts';
import { PlaylistPicker } from '../organizer/PlaylistPicker';
import { NotesToggle, TrackNotesPanel } from '../organizer/TrackNotes';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';

export interface ComparisonDeckProps {
  track: TrackInfo;
  playlistId: number;
  /** Key that picks this deck ("1" or "2"). */
  shortcut: string;
  /** This deck's track is the player's current track. */
  isLive: boolean;
  isPlaying: boolean;
  isBusy: boolean;
  onTogglePlay: () => void;
  onPick: () => void;
  onSkip: () => void;
  /** Omitted when the playlist can't drop tracks (smart playlists). */
  onRemove?: () => void;
  onTrackUpdate: (track: TrackInfo) => void;
}

function RatingLine({ track }: { track: TrackInfo }): JSX.Element {
  const rating = track.playlist_rating ?? track.rating;
  const settled = track.comparison_count >= 10;
  return (
    <span
      className={`tabular-nums ${settled ? 'text-amber-400/80' : 'text-white/40'}`}
      title={`Playlist rating from ${track.comparison_count} comparisons`}
    >
      {rating.toFixed(0)}
      <span className="text-white/30 ml-2">
        <span className="text-obsidian-accent/80">{track.wins}W</span>{' '}
        <span className="text-rose-400/70">{track.losses}L</span>
      </span>
    </span>
  );
}

interface DeckMenuProps {
  onSkip: () => void;
  onRemove?: () => void;
  disabled: boolean;
}

const menuItemClass = 'text-xs cursor-pointer focus:bg-white/10 focus:text-white';

function DeckMenu({ onSkip, onRemove, disabled }: DeckMenuProps): JSX.Element {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="More actions"
        className="p-1 rounded-sm text-white/40 hover:text-white/80 hover:bg-white/5 transition-colors"
      >
        <MoreHorizontal className="w-4 h-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52 bg-obsidian-surface border-obsidian-border text-white/80">
        <DropdownMenuItem className={menuItemClass} onSelect={onSkip} disabled={disabled}>
          <SkipForward className="w-3.5 h-3.5 mr-2 text-white/50" /> Skip this pair
          <kbd className="ml-auto px-1.5 rounded-sm bg-white/10 text-[10px] text-white/60">S</kbd>
        </DropdownMenuItem>
        {onRemove && (
          <>
            <DropdownMenuSeparator className="bg-obsidian-border" />
            <DropdownMenuItem
              className={`${menuItemClass} text-rose-400 focus:text-rose-300`}
              onSelect={onRemove}
              disabled={disabled}
            >
              <Trash2 className="w-3.5 h-3.5 mr-2" /> Remove from playlist
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function PickStrip({ shortcut, isLive, disabled, onPick }: {
  shortcut: string; isLive: boolean; disabled: boolean; onPick: () => void;
}): JSX.Element {
  const tone = isLive
    ? 'text-obsidian-accent bg-obsidian-accent/10 hover:bg-obsidian-accent/20'
    : 'text-white/70 bg-white/[0.02] hover:bg-white/5 hover:text-white';
  return (
    <button
      type="button"
      onClick={onPick}
      disabled={disabled}
      className={`relative flex sm:flex-col items-center justify-center gap-2 py-3 sm:py-0 sm:w-28
        border-t sm:border-t-0 sm:border-l border-obsidian-border rounded-b-lg sm:rounded-bl-none sm:rounded-r-lg
        font-semibold text-sm transition-colors disabled:opacity-50
        focus-visible:outline-2 focus-visible:outline-obsidian-accent ${tone}`}
    >
      Pick this
      <kbd className="hidden md:inline px-1.5 py-0.5 rounded-sm bg-white/10 text-[11px] text-white/60 font-normal">
        {shortcut}
      </kbd>
    </button>
  );
}

/** One side of a comparison: organizer-style banner, full-width waveform, pick strip. */
export function ComparisonDeck(props: ComparisonDeckProps): JSX.Element {
  const { track, isLive, isBusy } = props;
  const [notesOpen, setNotesOpen] = useState(false);

  return (
    <section
      aria-label={`Track ${props.shortcut}: ${track.title}`}
      className={`relative flex flex-col sm:flex-row bg-obsidian-surface border rounded-lg transition-colors ${
        isLive ? 'border-obsidian-accent/45' : 'border-obsidian-border'
      }`}
    >
      <Backdrop artworkUrl={track.artwork_url} title={track.title} />
      <div className="relative flex-1 min-w-0 p-4">
        <TrackBannerInfo
          trackId={track.id}
          title={track.title}
          artist={track.artist}
          artworkUrl={track.artwork_url}
          trackDate={track.added_at}
          reposters={track.reposters}
          scLiked={track.sc_liked}
          soundcloudUrl={track.soundcloud_url}
          bpm={track.bpm}
          keySignature={track.key_signature}
          genre={track.genre}
          onGenreChange={(genre) => props.onTrackUpdate({ ...track, genre: genre ?? undefined })}
          emojis={track.emojis}
          onEmojisChange={(emojis) => props.onTrackUpdate({ ...track, emojis })}
          titleAccessory={<DeckMenu onSkip={props.onSkip} onRemove={props.onRemove} disabled={isBusy} />}
        />
        <div className="h-16 my-3">
          <WaveformPlayer track={track} isPlaying={props.isPlaying} onTogglePlayPause={props.onTogglePlay} />
        </div>
        <div className="flex items-center gap-1 text-xs">
          <RatingLine track={track} />
          <div className="ml-auto flex items-center gap-1">
            <PlaylistPicker key={track.id} trackId={track.id} excludePlaylistId={props.playlistId} />
            <NotesToggle open={notesOpen} onToggle={() => setNotesOpen((prev) => !prev)} />
          </div>
        </div>
        {notesOpen && <TrackNotesPanel trackId={track.id} />}
      </div>
      <PickStrip shortcut={props.shortcut} isLive={isLive} disabled={isBusy} onPick={props.onPick} />
    </section>
  );
}
