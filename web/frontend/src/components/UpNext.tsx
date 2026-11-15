import { upcomingStart } from '@music-minion/shared';
import { usePlayerStore } from '../stores/playerStore';
import type { Track } from '../api/builder';

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return mins + ':' + secs.toString().padStart(2, '0');
}

interface UpNextTrackProps {
  track: Track;
  index: number;
  onPlay: () => void;
}

/** Click jumps playback to this queue position (POST /player/jump). */
function UpNextTrack({ track, index, onPlay }: UpNextTrackProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onPlay}
      aria-label={`Play ${track.title ?? 'track'}`}
      className="w-full text-left flex items-center gap-3 py-2 px-3 hover:bg-white/5 transition-colors border-l border-transparent hover:border-obsidian-accent/30"
    >
      <span className="text-white/40 text-sm font-sf-mono w-5">{index + 1}</span>
      <div className="flex-1 min-w-0">
        <p className="text-white/90 text-sm truncate">
          {track.title ?? 'Unknown Title'}
        </p>
        <p className="text-white/50 font-sf-mono text-xs truncate">
          {track.artist ?? 'Unknown Artist'}
        </p>
      </div>
      <span className="text-white/50 font-sf-mono text-xs shrink-0">
        {formatDuration(track.duration ?? null)}
      </span>
    </button>
  );
}

export function UpNext(): JSX.Element {
  const { queue, jumpTo } = usePlayerStore();
  // First upcoming index; current-track aware like the server (organizer can
  // displace the playing track from the queue).
  const start = usePlayerStore(upcomingStart);
  const upcoming = queue.slice(start, start + 5);

  return (
    <div className="bg-obsidian-surface border border-obsidian-border p-4">
      <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3 font-sf-mono">
        Up Next
      </h3>
      {upcoming.length > 0 ? (
        <div className="space-y-1">
          {upcoming.map((track, i) => (
            <UpNextTrack key={track.id} track={track} index={i} onPlay={() => void jumpTo(start + i)} />
          ))}
        </div>
      ) : (
        <p className="text-white/40 text-sm font-sf-mono">Queue is empty</p>
      )}
    </div>
  );
}
