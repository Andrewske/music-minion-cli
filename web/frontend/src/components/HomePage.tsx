import { useState, useCallback, useEffect } from 'react';
import { Music } from 'lucide-react';
import { usePlayerStore, type PlayContext } from '../stores/playerStore';
import type { Track } from '../api/builder';
import type { SortingState } from '@tanstack/react-table';
import { TrackDisplay } from './builder/TrackDisplay';
import { WaveformPlayer } from './WaveformPlayer';
import { TrackQueueTable } from './builder/TrackQueueTable';
import { usePlaylists } from '../hooks/usePlaylists';

export function HomePage(): JSX.Element {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [isLoadingPlayback] = useState(false);

  const {
    currentTrack,
    queue,
    queueIndex,
    isPlaying,
    currentContext,
    pause,
    resume,
    next,
    play,
    setSortOrder
  } = usePlayerStore();

  const { data: playlistsData } = usePlaylists();

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

  const handleWaveformFinish = useCallback((): void => {
    // Auto-advance to next track
    next();
  }, [next]);

  const handleEmojiUpdate = useCallback((updatedTrack: { id: number; emojis?: string[] }): void => {
    // Update both currentTrack and the matching track in queue
    if (currentTrack && currentTrack.id === updatedTrack.id) {
      const newTrack = { ...currentTrack, emojis: updatedTrack.emojis };
      const newQueue = queue.map(t =>
        t.id === updatedTrack.id ? { ...t, emojis: updatedTrack.emojis } : t
      );
      usePlayerStore.getState().set({ currentTrack: newTrack, queue: newQueue });
    }
  }, [currentTrack, queue]);

  const handleTrackClick = useCallback((track: Track): void => {
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

  const handleSortingChange = useCallback((newSorting: SortingState): void => {
    // Update local state for UI indicators
    setSorting(newSorting);

    // Call backend to sort and rebuild queue
    if (newSorting.length > 0) {
      const { id, desc } = newSorting[0];
      setSortOrder(id, desc ? 'desc' : 'asc');
    }
  }, [setSortOrder]);

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
          if (isPlaying) {
            pause();
          } else {
            resume();
          }
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
              <TrackDisplay track={currentTrack} onEmojiUpdate={handleEmojiUpdate} />
              <div className="h-16 border-t border-b border-obsidian-border">
                <WaveformPlayer
                  track={currentTrack}
                  isPlaying={isPlaying}
                  onTogglePlayPause={() => isPlaying ? pause() : resume()}
                  onFinish={handleWaveformFinish}
                />
              </div>
            </div>

            {/* Queue Table */}
            {queue.length > 0 ? (
              <TrackQueueTable
                tracks={queue}
                queueIndex={queueIndex}
                nowPlayingId={currentTrack?.id ?? null}
                onTrackClick={handleTrackClick}
                sorting={sorting}
                onSortingChange={handleSortingChange}
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
            <p className="text-white/40 text-sm">Select a playlist to start listening</p>
          </section>
        )}
      </div>
    </div>
  );
}

