import { useState, useEffect } from 'react';
import { useSmartPlaylistEditor } from '../hooks/useSmartPlaylistEditor';
import FilterPanel from '../components/builder/FilterPanel';
import { TrackQueueTable } from '../components/builder/TrackQueueTable';
import { WaveformPlayer } from '../components/WaveformPlayer';
import type { Track } from '../api/builder';

interface SmartPlaylistEditorProps {
  playlistId: number;
  playlistName: string;
}

export function SmartPlaylistEditor({ playlistId, playlistName }: SmartPlaylistEditorProps) {
  const {
    filters,
    tracks,
    updateFilters,
    isLoading,
    isUpdatingFilters,
    sorting,
    setSorting,
    skipTrack,
    skippedTracks,
    currentTrack,
    currentTrackIndex,
    nextTrack,
    previousTrack,
    isReviewMode,
    setIsReviewMode,
  } = useSmartPlaylistEditor(playlistId);
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Select first track when tracks load (filter mode only)
  useEffect(() => {
    if (!isReviewMode && tracks.length > 0 && !selectedTrack) {
      setSelectedTrack(tracks[0]);
    }
  }, [tracks, selectedTrack, isReviewMode]);

  // Initialize currentTrack when entering review mode
  useEffect(() => {
    if (isReviewMode && tracks.length > 0 && currentTrack === null) {
      nextTrack(); // Sets to first track
    }
  }, [isReviewMode, tracks.length, currentTrack, nextTrack]);

  // Keyboard shortcuts (space for play/pause, 0-9 for seek)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === ' ') {
        e.preventDefault();
        setIsPlaying(prev => !prev);
      }
      if (e.key >= '0' && e.key <= '9') {
        const percent = parseInt(e.key) * 10;
        window.dispatchEvent(new CustomEvent('music-minion-seek-percent', { detail: percent }));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="text-slate-400">Loading smart playlist...</div>
      </div>
    );
  }

  // Handle skip track in review mode
  const handleSkip = async () => {
    if (!currentTrack || skipTrack.isPending) return;

    await skipTrack.mutateAsync(currentTrack.id);

    // After skip, track is removed from array, so currentTrackId now points to next track
    // If this was the last track, exit review mode
    if (tracks.length <= 1) {
      setIsReviewMode(false);
    }
    // Note: No need to call nextTrack() - the mutation invalidates the query,
    // and currentTrackId stays the same but now points to what was the next track
  };

  // Handle keep track in review mode (just advance without skipping)
  const handleKeep = () => {
    if (!currentTrack) return;
    nextTrack();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="flex justify-between items-center mb-4 px-6 pt-6">
        <h2 className="text-xl font-semibold">
          <span className="text-purple-400">[Smart]</span> {playlistName}
        </h2>
        <div className="flex items-center gap-4">
          <span className="text-slate-400">{tracks.length} tracks match</span>
          <button
            onClick={() => setIsReviewMode(!isReviewMode)}
            disabled={tracks.length === 0}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:text-slate-500 rounded transition-colors"
          >
            {isReviewMode ? 'Filter Mode' : 'Review Mode'}
          </button>
        </div>
      </div>

      {isReviewMode ? (
        // Review Mode View
        <div className="px-6 pb-6">
          {currentTrack ? (
            <div className="bg-slate-900 rounded-lg p-8 max-w-4xl mx-auto">
              {/* Progress indicator */}
              <div className="text-center mb-6">
                <p className="text-slate-400 text-sm">
                  Track {currentTrackIndex + 1} of {tracks.length}
                </p>
              </div>

              {/* Track display */}
              <div className="text-center mb-6">
                <h2 className="text-4xl font-bold mb-2">{currentTrack.title}</h2>
                <p className="text-2xl text-gray-300 mb-4">{currentTrack.artist}</p>
                {currentTrack.album && <p className="text-xl text-gray-400 mb-6">{currentTrack.album}</p>}
                <div className="flex gap-4 justify-center flex-wrap">
                  {currentTrack.genre && <span className="px-3 py-1 bg-purple-600 rounded-full">{currentTrack.genre}</span>}
                  {currentTrack.year && <span className="px-3 py-1 bg-blue-600 rounded-full">{currentTrack.year}</span>}
                  {currentTrack.bpm && <span className="px-3 py-1 bg-orange-600 rounded-full">{Math.round(currentTrack.bpm)} BPM</span>}
                  {currentTrack.key_signature && <span className="px-3 py-1 bg-green-600 rounded-full">{currentTrack.key_signature}</span>}
                  {currentTrack.emojis && currentTrack.emojis.length > 0 && (
                    <span className="px-3 py-1 bg-slate-700 rounded-full">{currentTrack.emojis.join(' ')}</span>
                  )}
                </div>
              </div>

              {/* Waveform player */}
              <div className="h-20 mb-6">
                <WaveformPlayer
                  track={{
                    id: currentTrack.id,
                    title: currentTrack.title,
                    artist: currentTrack.artist,
                    rating: currentTrack.elo_rating || 0,
                    comparison_count: 0,
                    wins: 0,
                    losses: 0,
                    has_waveform: true,
                  }}
                  isPlaying={isPlaying}
                  onTogglePlayPause={() => setIsPlaying(!isPlaying)}
                  onFinish={() => setIsPlaying(false)}
                />
              </div>

              {/* Navigation and action buttons */}
              <div className="flex gap-4 justify-center items-center mb-4">
                <button
                  onClick={previousTrack}
                  className="px-6 py-3 border border-white/20 text-white/60 hover:border-white/40 hover:text-white transition-all text-sm"
                >
                  Previous
                </button>
                <button
                  onClick={handleSkip}
                  disabled={skipTrack.isPending}
                  className="px-8 py-3 border border-red-600 text-red-600 hover:bg-red-600 hover:text-white disabled:opacity-30 transition-all text-sm tracking-wider"
                >
                  {skipTrack.isPending ? '...' : 'Skip'}
                </button>
                <button
                  onClick={handleKeep}
                  className="px-8 py-3 border border-green-600 text-green-600 hover:bg-green-600 hover:text-white transition-all text-sm tracking-wider"
                >
                  Keep
                </button>
                <button
                  onClick={nextTrack}
                  className="px-6 py-3 border border-white/20 text-white/60 hover:border-white/40 hover:text-white transition-all text-sm"
                >
                  Next
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 rounded-lg p-8 text-center max-w-4xl mx-auto">
              <h3 className="text-2xl font-bold mb-2">All tracks reviewed</h3>
              <p className="text-gray-400">No more tracks to review</p>
            </div>
          )}
        </div>
      ) : (
        // Filter Mode View
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 px-6 pb-6">
          {/* Left Panel: Filters */}
          <aside className="md:col-span-1 bg-slate-900 rounded-lg p-4">
            <FilterPanel
              filters={filters}
              onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
              isUpdating={isUpdatingFilters}
              playlistId={playlistId}
            />

            {/* View Skipped button */}
            {skippedTracks.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-700">
                <button
                  onClick={() => {
                    // TODO: Task 06 will implement SkippedTracksDialog
                    alert(`${skippedTracks.length} skipped tracks (dialog coming in Task 06)`);
                  }}
                  className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors text-sm"
                >
                  View Skipped ({skippedTracks.length})
                </button>
              </div>
            )}
          </aside>

          {/* Center: Track display and player */}
          <main className="md:col-span-3">
            {selectedTrack ? (
              <div className="bg-slate-900 rounded-lg p-8">
                {/* Track display */}
                <div className="text-center mb-6">
                  <h2 className="text-4xl font-bold mb-2">{selectedTrack.title}</h2>
                  <p className="text-2xl text-gray-300 mb-4">{selectedTrack.artist}</p>
                  {selectedTrack.album && <p className="text-xl text-gray-400 mb-6">{selectedTrack.album}</p>}
                  <div className="flex gap-4 justify-center flex-wrap">
                    {selectedTrack.genre && <span className="px-3 py-1 bg-purple-600 rounded-full">{selectedTrack.genre}</span>}
                    {selectedTrack.year && <span className="px-3 py-1 bg-blue-600 rounded-full">{selectedTrack.year}</span>}
                    {selectedTrack.bpm && <span className="px-3 py-1 bg-orange-600 rounded-full">{selectedTrack.bpm} BPM</span>}
                    {selectedTrack.key_signature && <span className="px-3 py-1 bg-green-600 rounded-full">{selectedTrack.key_signature}</span>}
                  </div>
                </div>

                {/* Waveform player */}
                <div className="h-20 mb-6">
                  <WaveformPlayer
                    track={{
                      id: selectedTrack.id,
                      title: selectedTrack.title,
                      artist: selectedTrack.artist,
                      rating: selectedTrack.elo_rating || 0,
                      comparison_count: 0,
                      wins: 0,
                      losses: 0,
                      has_waveform: true,
                    }}
                    isPlaying={isPlaying}
                    onTogglePlayPause={() => setIsPlaying(!isPlaying)}
                    onFinish={() => setIsPlaying(false)}
                  />
                </div>

                {/* Track list */}
                <div className="mt-8">
                  <TrackQueueTable
                    tracks={tracks}
                    queueIndex={tracks.findIndex(t => t.id === selectedTrack?.id)}
                    nowPlayingId={selectedTrack?.id ?? null}
                    onTrackClick={(track) => {
                      setSelectedTrack(track);
                      setIsPlaying(true);
                    }}
                    sorting={sorting}
                    onSortingChange={setSorting}
                    onLoadMore={() => {}}
                    hasMore={false}
                    isLoadingMore={false}
                  />
                </div>
              </div>
            ) : (
              <div className="bg-slate-900 rounded-lg p-8 text-center">
                {filters.length === 0 ? (
                  <>
                    <h3 className="text-2xl font-bold mb-2">Add filters to define your smart playlist</h3>
                    <p className="text-gray-400">Use the filter panel to specify which tracks belong in this playlist</p>
                  </>
                ) : (
                  <>
                    <h3 className="text-2xl font-bold mb-2">No tracks match your criteria</h3>
                    <p className="text-gray-400">Try adjusting or removing some filters</p>
                  </>
                )}
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
