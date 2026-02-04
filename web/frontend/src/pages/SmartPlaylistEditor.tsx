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
  } = useSmartPlaylistEditor(playlistId);
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Select first track when tracks load
  useEffect(() => {
    if (tracks.length > 0 && !selectedTrack) {
      setSelectedTrack(tracks[0]);
    }
  }, [tracks, selectedTrack]);

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

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="flex justify-between items-center mb-4 px-6 pt-6">
        <h2 className="text-xl font-semibold">
          <span className="text-purple-400">[Smart]</span> {playlistName}
        </h2>
        <span className="text-slate-400">{tracks.length} tracks match</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 px-6 pb-6">
        {/* Left Panel: Filters */}
        <aside className="md:col-span-1 bg-slate-900 rounded-lg p-4">
          <FilterPanel
            filters={filters}
            onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
            isUpdating={isUpdatingFilters}
            playlistId={playlistId}
          />
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

              {/* NO add/skip buttons for smart playlists */}

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
    </div>
  );
}
