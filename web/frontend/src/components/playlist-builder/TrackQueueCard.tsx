import type { Track } from '../../api/builder';

interface TrackQueueCardProps {
  track: Track;
  isQueue: boolean;
  isPlaying: boolean;
  onClick: () => void;
}

export function TrackQueueCard({ track, isQueue, isPlaying, onClick }: TrackQueueCardProps): JSX.Element {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left py-3 border-b border-obsidian-border hover:bg-white/5 transition-colors
        ${isPlaying ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent' : ''}
        ${isQueue && !isPlaying ? 'bg-white/5' : ''}`}
    >
      <p className="text-xs text-white/60 truncate">{track.artist}</p>
      <p className="text-sm font-medium text-white truncate">{track.title}</p>
      <div className="flex items-center gap-2 mt-1 text-xs text-white/40">
        {track.bpm && <span>{Math.round(track.bpm)} BPM</span>}
        {track.key_signature && <span>{track.key_signature}</span>}
        {track.genre && <span>{track.genre}</span>}
        {track.year && <span>{track.year}</span>}
      </div>
    </button>
  );
}
