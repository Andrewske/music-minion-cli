import { usePlayer } from '../hooks/usePlayer';
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
}

function UpNextTrack({ track, index }: UpNextTrackProps): JSX.Element {
  return (
    <div className="flex items-center gap-3 py-2 px-3 hover:bg-white/5 transition-colors border-l border-transparent hover:border-obsidian-accent/30">
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
    </div>
  );
}

export function UpNext(): JSX.Element {
  const { queue, queueIndex } = usePlayer();

  // Get upcoming tracks (next 5 after current)
  const upcoming = queue.slice(queueIndex + 1, queueIndex + 6);

  return (
    <div className="bg-obsidian-surface border border-obsidian-border p-4">
      <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3 font-sf-mono">
        Up Next
      </h3>
      {upcoming.length > 0 ? (
        <div className="space-y-1">
          {upcoming.map((track, i) => (
            <UpNextTrack key={track.id} track={track} index={i} />
          ))}
        </div>
      ) : (
        <p className="text-white/40 text-sm font-sf-mono">Queue is empty</p>
      )}
    </div>
  );
}
