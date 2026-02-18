import { useState, useCallback, useEffect } from 'react';
import { Music } from 'lucide-react';
import { usePlayerStore, type PlayContext } from '../stores/playerStore';
import { useQuery } from '@tanstack/react-query';
import { getStations, type Station } from '../api/radio';
import type { Track } from '../api/builder';
import type { SortingState } from '@tanstack/react-table';
import { TrackDisplay } from './builder/TrackDisplay';
import { WaveformSection } from './builder/WaveformSection';
import { TrackQueueTable } from './builder/TrackQueueTable';
import { usePlaylists } from '../hooks/usePlaylists';

export function HomePage(): JSX.Element {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [isLoadingPlayback, setIsLoadingPlayback] = useState(false);

  const {
    currentTrack,
    queue,
    queueIndex,
    isPlaying,
    currentContext,
    pause,
    resume,
    next,
    play
  } = usePlayerStore();

  const { data: playlistsData } = usePlaylists();

  const { data: stations } = useQuery({
    queryKey: ['stations'],
    queryFn: getStations,
  });

  function getContextTitle(context: PlayContext | null): string {
    if (!context) return 'Queue';

    if (context.type === 'playlist' && context.playlist_id) {
      const playlist = playlistsData?.find(p => p.id === context.playlist_id);
      return playlist?.name || `Playlist #${context.playlist_id}`;
    }

    switch (context.type) {
      case 'builder': return 'Builder';
      case 'search': return `Search: ${context.query}`;
      case 'comparison': return 'Comparison';
      case 'track': return 'Track';
      default: return 'Queue';
    }
  }

  const handleWaveformFinish = useCallback((_targetDeviceId?: string): void => {
    // Auto-advance to next track
    next();
  }, [next]);

  const handleTrackClick = useCallback((track: Track, _targetDeviceId?: string): void => {
    if (!currentContext) return;

    const trackIndex = queue.findIndex(t => t.id === track.id);
    if (trackIndex >= 0) {
      // Play from clicked position, preserve context
      play(track, {
        ...currentContext,
        start_index: trackIndex
      });
    }
  }, [queue, currentContext, play]);

  // Spacebar play/pause keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      // Only trigger if not typing in an input/textarea
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        if (currentTrack) {
          isPlaying ? pause() : resume();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentTrack, isPlaying, pause, resume]);

  return (
    <div className="min-h-screen bg-black font-inter text-white">
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-4 md:py-8">
        {/* Header with context info and queue position */}
        <div className="mb-6">
          <p className="text-white/40 text-sm font-sf-mono mb-1">Now Playing</p>
          <div className="flex items-center gap-3">
            <h1 className="text-xl text-white/60">{getContextTitle(currentContext)}</h1>
            {currentTrack && queue.length > 0 && (
              <span className="text-white/40 text-sm font-sf-mono">
                Track {queueIndex + 1} of {queue.length}
              </span>
            )}
          </div>
        </div>

        {isLoadingPlayback ? (
          <div className="py-20 text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-obsidian-accent border-r-transparent mb-4"></div>
            <p className="text-white/40 text-sm">Loading playback...</p>
          </div>
        ) : currentTrack ? (
          <div className="space-y-6 md:space-y-12">
            {/* Sticky player section on mobile */}
            <div className="sticky top-10 md:static z-10 bg-black pb-4 md:pb-0">
              <TrackDisplay track={currentTrack} />
              <WaveformSection
                track={currentTrack}
                isPlaying={isPlaying}
                loopEnabled={false}
                onTogglePlayPause={() => isPlaying ? pause() : resume()}
                onLoopChange={() => {}} // no-op - loop disabled on home page
                onFinish={handleWaveformFinish}
              />
            </div>

            {/* Queue Table */}
            {queue.length > 0 ? (
              <TrackQueueTable
                tracks={queue}
                queueIndex={queueIndex}
                nowPlayingId={currentTrack?.id ?? null}
                onTrackClick={handleTrackClick}
                sorting={sorting}
                onSortingChange={setSorting}
                onLoadMore={() => {}} // no-op - queue is fully loaded
                hasMore={false}
                isLoadingMore={false}
              />
            ) : (
              <div className="border-t border-obsidian-border py-8 text-center">
                <p className="text-white/40 text-sm">No tracks in queue</p>
              </div>
            )}
          </div>
        ) : (
          <section className="py-20 text-center">
            <Music className="h-12 w-12 mx-auto text-white/20 mb-4" />
            <h2 className="text-lg font-medium text-white/60 mb-2">Nothing playing</h2>
            <p className="text-white/40 text-sm">Select a playlist or station to start</p>

            {/* Station quick access */}
            {stations && stations.length > 0 && (
              <div className="mt-8">
                <h3 className="text-sm text-white/40 mb-4">Quick Start</h3>
                <div className="flex flex-wrap gap-2 justify-center">
                  {stations.map(station => <StationChip key={station.id} station={station} setIsLoadingPlayback={setIsLoadingPlayback} />)}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function StationChip({ station, setIsLoadingPlayback }: { station: Station; setIsLoadingPlayback: (loading: boolean) => void }): JSX.Element {
  const { play } = usePlayerStore();

  const handleClick = async (): Promise<void> => {
    setIsLoadingPlayback(true);

    try {
      const response = await fetch(`/api/playlists/${station.playlist_id}/tracks`);
      if (!response.ok) {
        console.error('Failed to fetch station playlist tracks');
        return;
      }
      const data = await response.json();
      const tracks: Track[] = data.tracks;

      if (tracks.length > 0) {
        await play(tracks[0], {
          type: 'playlist',
          playlist_id: station.playlist_id,
          start_index: 0,
          shuffle: station.shuffle_enabled,
        });
      }
    } finally {
      // Reset loading after a delay to prevent flashing
      setTimeout(() => setIsLoadingPlayback(false), 500);
    }
  };

  return (
    <button
      onClick={handleClick}
      className="px-4 py-2 bg-card rounded-full hover:bg-accent transition-colors"
    >
      {station.name}
    </button>
  );
}
