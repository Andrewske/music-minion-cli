import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getNowPlaying } from '../api/radio';
import type { NowPlaying, TrackInfo } from '../api/radio';
import { EmojiTrackActions } from './EmojiTrackActions';

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return mins + ':' + secs.toString().padStart(2, '0');
}

interface UpNextTrackProps {
  track: TrackInfo;
  index: number;
  onUpdate: (updatedTrack: { id: number; emojis?: string[] }) => void;
}

function UpNextTrack({ track, index, onUpdate }: UpNextTrackProps): JSX.Element {
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
      <EmojiTrackActions track={track} onUpdate={onUpdate} compact />
      <span className="text-white/50 font-sf-mono text-xs shrink-0">
        {formatDuration(track.duration)}
      </span>
    </div>
  );
}

export function UpNext(): JSX.Element {
  const queryClient = useQueryClient();
  const { data: nowPlaying, isLoading, error } = useQuery<NowPlaying>({
    queryKey: ['nowPlaying'],
    queryFn: getNowPlaying,
    refetchInterval: 5000,
    retry: 1,
  });

  const handleTrackUpdate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['nowPlaying'] });
  };

  if (isLoading) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border p-4 animate-pulse">
        <div className="h-4 bg-obsidian-border w-24 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-3 py-2">
              <div className="w-5 h-4 bg-obsidian-border" />
              <div className="flex-1 space-y-1">
                <div className="h-4 bg-obsidian-border w-3/4" />
                <div className="h-3 bg-obsidian-border w-1/2" />
              </div>
              <div className="w-10 h-4 bg-obsidian-border" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !nowPlaying) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border p-4">
        <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3 font-sf-mono">
          Up Next
        </h3>
        <p className="text-white/40 text-sm font-sf-mono">No upcoming tracks</p>
      </div>
    );
  }

  const upcomingTracks = nowPlaying.upcoming.slice(0, 5);

  if (upcomingTracks.length === 0) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border p-4">
        <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3 font-sf-mono">
          Up Next
        </h3>
        <p className="text-white/40 text-sm font-sf-mono">No upcoming tracks</p>
      </div>
    );
  }

  return (
    <div className="bg-obsidian-surface border border-obsidian-border p-4">
      <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3 font-sf-mono">
        Up Next
      </h3>
      <div className="space-y-1">
        {upcomingTracks.map((track, index) => (
          <UpNextTrack key={track.id} track={track} index={index} onUpdate={handleTrackUpdate} />
        ))}
      </div>
    </div>
  );
}
