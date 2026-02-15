import type { TrackInfo } from '../types';
import { EmojiTrackActions } from './EmojiTrackActions';
import { usePlayer } from '../hooks/usePlayer';
import type { PlayContext } from '../stores/playerStore';

interface TrackCardProps {
  onClick?: () => void;
  track: TrackInfo;
  isPlaying: boolean;
  className?: string;
  onArchive?: () => void;
  onWinner?: () => void;
  isLoading?: boolean;
  rankingMode?: 'global' | 'playlist';
  onTrackUpdate?: (track: TrackInfo) => void;
  context?: PlayContext;
}

export function TrackCard({ track, isPlaying, className = '', onArchive, onWinner, onClick, isLoading, rankingMode = 'global', onTrackUpdate, context }: TrackCardProps) {
  const { play } = usePlayer();

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (context) {
      // Convert TrackInfo to Track format for player
      play({
        id: track.id,
        title: track.title,
        artist: track.artist ?? 'Unknown Artist',
        album: track.album,
        genre: track.genre,
        year: track.year,
        bpm: track.bpm,
        duration: track.duration,
      }, context);
    }
  };

  const renderRatingBadge = (rating: number, wins: number, losses: number, comparisonCount: number) => {
    const isBootstrap = comparisonCount < 10;

    // Check if we have playlist-specific ratings
    const hasPlaylistRating = track.playlist_rating !== undefined && track.playlist_rating !== null;
    const displayRating = hasPlaylistRating ? (track.playlist_rating as number) : rating;

    return (
      <div className={`
        flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border backdrop-blur-sm
        transition-colors duration-300
        ${isBootstrap
          ? 'bg-obsidian-surface/50 border-obsidian-border text-white/40'
          : 'bg-amber-950/20 border-amber-500/20 text-amber-400'}
      `}>
        {/* Icon & Score */}
        <div className="flex items-center gap-1.5">
          <span className={isBootstrap ? 'opacity-70' : ''}>
            {hasPlaylistRating ? '🎯' : (isBootstrap ? '🎵' : '⭐')}
          </span>
          <span className="font-bold tabular-nums tracking-tight">
            {displayRating.toFixed(0)}
          </span>
          {hasPlaylistRating && (
            <span className="text-xs text-slate-500 ml-1">
              (Global: {rating.toFixed(0)})
            </span>
          )}
        </div>

        {/* Divider */}
        <div className={`w-px h-3 ${isBootstrap ? 'bg-obsidian-border' : 'bg-amber-500/20'}`} />

        {/* Win/Loss Record */}
        <div className="flex items-center gap-1 text-xs font-medium tabular-nums">
           <span className="text-obsidian-accent">{wins}</span>
           <span className={`${isBootstrap ? 'text-white/30' : 'text-amber-500/40'}`}>/</span>
           <span className="text-rose-500">{losses}</span>
        </div>
      </div>
    );
  };

  return (
    <div
      className={`
        relative overflow-hidden
        bg-obsidian-surface border border-obsidian-border
        transition-all duration-300
        hover:border-obsidian-accent/30 hover:bg-white/5
        active:scale-[0.98]
        group
        flex flex-col
        ${isPlaying ? 'ring-2 ring-obsidian-accent/50' : ''}
        ${className}
      `}
    >
      {/* Background Glow Effect for playing state */}
      {isPlaying && (
        <div className="absolute inset-0 bg-gradient-to-t from-obsidian-accent/5 to-transparent pointer-events-none" />
      )}

      {/* Clickable content area */}
      <button
        type="button"
        onClick={handleClick}
        className="cursor-pointer flex flex-col w-full text-left"
      >
        <div className="p-4 flex flex-col items-center justify-center text-center relative z-10">
          <div className="flex-1 pt-2">
            {/* Title & Artist */}
            <h3 className="font-bold text-xl text-white/90 leading-tight mb-2 line-clamp-2">
              {track.title}
            </h3>
            <p className="text-lg text-obsidian-accent font-medium mb-2 line-clamp-1">
              {track.artist}
            </p>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-white/50 font-sf-mono mb-2">
              <span className="min-h-[1rem]">{track.year ?? '----'}</span>
              <span className="min-h-[1rem]">{track.bpm ? `${track.bpm} BPM` : '--- BPM'}</span>
              <span className="col-span-2 min-h-[1rem]">{track.genre ?? 'Unknown genre'}</span>
            </div>
          </div>

          {/* Stats / Badges */}
          <div className="pt-4 border-t border-obsidian-border w-full flex flex-col items-center gap-3">
            {renderRatingBadge(track.rating, track.wins, track.losses, track.comparison_count)}
          </div>
        </div>
      </button>

      {/* Emoji Tags - outside clickable area */}
      {onTrackUpdate && (
        <div className="px-4 pb-3" onClick={(e) => e.stopPropagation()}>
          <EmojiTrackActions
            track={track}
            onUpdate={(updated) => onTrackUpdate({ ...track, emojis: updated.emojis })}
          />
        </div>
      )}

      {/* Action Buttons - separate from clickable area */}
      {(onArchive && onWinner) && (
        <div className="hidden lg:flex border-t border-obsidian-border">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onArchive(); }}
            disabled={isLoading}
            className="flex-1 py-2 text-sm font-medium text-rose-400/70 hover:text-rose-400 hover:bg-rose-500/10 transition-colors border-r border-obsidian-border disabled:opacity-50"
          >
            {rankingMode === 'playlist' ? '🗂️ Remove from playlist' : '🗂️ Archive'}
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onWinner(); }}
            disabled={isLoading}
            className="flex-1 py-2 text-sm font-medium text-obsidian-accent/70 hover:text-obsidian-accent hover:bg-obsidian-accent/10 transition-colors disabled:opacity-50"
          >
            🏆 Winner
          </button>
        </div>
      )}
    </div>
  );
}
