import type { Track } from '../../api/builder';
import { EmojiTrackActions } from '../EmojiTrackActions';

interface TrackDisplayProps {
  track: Track;
  onEmojiUpdate?: (track: { id: number; emojis?: string[] }) => void;
}

/**
 * Left-aligned track display for playlist builders (obsidian style).
 * Shows artist, title, album, and metadata pills with emoji reactions.
 */
export function TrackDisplay({ track, onEmojiUpdate }: TrackDisplayProps): JSX.Element {
  return (
    <div className="py-4 md:py-8">
      <p className="text-obsidian-accent text-sm font-sf-mono mb-2">{track.artist}</p>
      <h2 className="text-2xl md:text-4xl font-light text-white mb-2 md:mb-4">{track.title}</h2>
      {track.album && (
        <p className="text-white/30 text-sm">{track.album}</p>
      )}

      {/* Metadata pills */}
      <div className="flex flex-wrap items-center gap-2 md:gap-4 mt-4 md:mt-6">
        {track.bpm && (
          <span className="text-white/40 text-xs font-sf-mono">{Math.round(track.bpm)} BPM</span>
        )}
        {track.key_signature && (
          <span className="text-white/40 text-xs font-sf-mono">{track.key_signature}</span>
        )}
        {track.genre && (
          <span className="text-white/40 text-xs font-sf-mono">{track.genre}</span>
        )}
        {track.year && (
          <span className="text-white/40 text-xs font-sf-mono">{track.year}</span>
        )}
        {onEmojiUpdate && (
          <EmojiTrackActions
            track={{ id: track.id, emojis: track.emojis }}
            onUpdate={onEmojiUpdate}
          />
        )}
      </div>
    </div>
  );
}
