# Frontend: Smart Playlist Editor Component

## Files to Modify/Create
- `web/frontend/src/pages/SmartPlaylistEditor.tsx` (new)
- `web/frontend/src/pages/PlaylistBuilder.tsx` (modify)

## Implementation Details

### SmartPlaylistEditor Component (new)

Create a new component that reuses existing UI components but with smart playlist behavior:

```tsx
import { useState, useEffect } from 'react';
import type { SortingState } from '@tanstack/react-table';
import { useSmartPlaylistEditor } from '../hooks/useSmartPlaylistEditor';
import FilterPanel from '../components/builder/FilterPanel';
import { TrackQueueTable } from '../components/builder/TrackQueueTable';
import { WaveformPlayer } from '../components/WaveformPlayer';

interface SmartPlaylistEditorProps {
  playlistId: number;
  playlistName: string;
}

export function SmartPlaylistEditor({ playlistId, playlistName }: SmartPlaylistEditorProps) {
  const { filters, tracks, updateFilters, isLoading, isUpdatingFilters } = useSmartPlaylistEditor(playlistId);
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([{ id: 'artist', desc: false }]);

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
                  onLoadMore={() => {}}  // No pagination for now
                  hasMore={false}
                  isLoadingMore={false}
                />
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 rounded-lg p-8 text-center">
              <h3 className="text-2xl font-bold mb-2">No tracks match filters</h3>
              <p className="text-gray-400">Add or adjust filters to see matching tracks</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
```

### PlaylistBuilder Mode Switch (modify)

Update `PlaylistBuilder.tsx` to conditionally render based on playlist type:

```tsx
import { SmartPlaylistEditor } from './SmartPlaylistEditor';

interface PlaylistBuilderProps {
  playlistId: number;
  playlistName: string;
  playlistType: 'manual' | 'smart';  // Add this prop
}

export function PlaylistBuilder({ playlistId, playlistName, playlistType }: PlaylistBuilderProps) {
  // Route to smart editor for smart playlists
  if (playlistType === 'smart') {
    return <SmartPlaylistEditor playlistId={playlistId} playlistName={playlistName} />;
  }

  // Existing manual builder code continues below...
}
```

## Acceptance Criteria
- [ ] SmartPlaylistEditor displays filter panel (reuses FilterPanel component)
- [ ] Track list shows tracks matching filters (no add/skip buttons)
- [ ] Clicking a track selects it and plays in waveform player
- [ ] Filter changes refresh the track list
- [ ] Header shows "[Smart]" badge and track count
- [ ] PlaylistBuilder routes to SmartPlaylistEditor when `playlistType === 'smart'`
- [ ] Keyboard shortcuts work (space = play/pause, 0-9 = seek)

## Dependencies
- Task 03: useSmartPlaylistEditor hook must exist
