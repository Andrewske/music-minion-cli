---
task: 01-refactor-homepage-implementation
status: done
depends: []
files:
  - path: web/frontend/src/components/HomePage.tsx
    action: modify
---

# Refactor HomePage with Builder Components and Enhanced Features

## Context
Transform the Home page from a minimal now-playing display into a full-featured playback view using playlist-builder components (TrackDisplay, WaveformSection, TrackQueueTable). This refactor combines layout changes with handler implementations and UX enhancements.

## Files to Modify
- `web/frontend/src/components/HomePage.tsx` (modify - refactor from 110 lines to ~250 lines)

## Implementation Details

### 1. Add New Imports

```tsx
import { useState, useCallback, useEffect } from 'react';
import { Music } from 'lucide-react';
import { usePlayerStore } from '../stores/playerStore';
import { useQuery } from '@tanstack/react-query';
import { getStations, type Station } from '../api/radio';
import type { Track } from '../api/builder';
import type { SortingState } from '@tanstack/react-table';
import { TrackDisplay } from './builder/TrackDisplay';
import { WaveformSection } from './builder/WaveformSection';
import { TrackQueueTable } from './builder/TrackQueueTable';
import { usePlaylists } from '../hooks/usePlaylists';
```

### 2. Add State Variables

```tsx
const [loopEnabled, setLoopEnabled] = useState(() => {
  // Persist loop state to localStorage
  const saved = localStorage.getItem('music-minion-home-loop');
  return saved ? JSON.parse(saved) : false;
});

const [sorting, setSorting] = useState<SortingState>([]);
const [isLoadingPlayback, setIsLoadingPlayback] = useState(false);
```

### 3. Extract PlayerStore State and Actions

```tsx
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
```

### 4. Fetch Playlists for Title Lookup

```tsx
const { data: playlistsData } = usePlaylists();
```

### 5. Implement Context Title Helper

```tsx
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
```

### 6. Implement Waveform Finish Handler

```tsx
const handleWaveformFinish = useCallback((targetDeviceId?: string): void => {
  if (loopEnabled) {
    // Restart current track
    pause();
    setTimeout(() => resume(), 100);
  } else {
    // Auto-advance to next track
    next();
  }
}, [loopEnabled, pause, resume, next]);
```

**Note:** `targetDeviceId` parameter is unused but future-proofs for multi-device playback.

### 7. Implement Track Click Handler

```tsx
const handleTrackClick = useCallback((track: Track, targetDeviceId?: string): void => {
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
```

**Note:** `targetDeviceId` parameter is unused but future-proofs for multi-device playback.

### 8. Persist Loop State to localStorage

```tsx
useEffect(() => {
  localStorage.setItem('music-minion-home-loop', JSON.stringify(loopEnabled));
}, [loopEnabled]);
```

### 9. Implement Spacebar Play/Pause Keyboard Shortcut

```tsx
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
```

### 10. Update StationChip with Loading State

Modify the `StationChip` component's `handleClick` to set loading state:

```tsx
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
```

### 11. Replace Main Layout Structure

```tsx
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
              loopEnabled={loopEnabled}
              onTogglePlayPause={() => isPlaying ? pause() : resume()}
              onLoopChange={setLoopEnabled}
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
                {stations.map(station => <StationChip key={station.id} station={station} />)}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  </div>
);
```

### 12. Future-Proofing: Add data-track-id Attributes

In the `TrackQueueTable` component integration, note that TanStack React Table automatically includes row data. For future drag-to-reorder or context menu features, the track ID is already accessible via the row model.

No additional attributes needed in this task - the table component handles this internally.

### 13. Click-to-Seek on Waveform

Verify that `WaveformPlayer` supports click-to-seek (it should via wavesurfer.js). Test by clicking different positions on the waveform. If not working, check `useWavesurfer` hook implementation.

## Theme Consistency

**Obsidian theme classes:**
- Background: `bg-black`
- Borders: `border-obsidian-border`
- Accent: `text-obsidian-accent`, `border-obsidian-accent`
- Typography: `font-inter` (body), `font-sf-mono` (metadata)
- Spacing: `space-y-6 md:space-y-12`

**Loading spinner:** Uses `border-obsidian-accent` with rotation animation

## Verification

1. Start the web frontend: `music-minion --web`
2. Navigate to Home page (`/`)
3. **Test empty state:**
   - Verify "Nothing playing" shows with stations
   - Click a station, verify loading spinner shows
   - Verify playback starts after ~500ms
4. **Test active playback:**
   - Start playback from playlist
   - Verify TrackDisplay shows metadata
   - Verify "Track X of Y" indicator in header
   - Verify playlist name shows in header
5. **Test loop persistence:**
   - Enable loop toggle
   - Refresh page
   - Verify loop is still enabled
6. **Test spacebar shortcut:**
   - Press spacebar, verify play/pause toggles
   - Click into an input field, press spacebar, verify it types a space (doesn't toggle)
7. **Test waveform:**
   - Click waveform to seek
   - Verify position updates
   - Click play/pause button
8. **Test queue interaction:**
   - Click a track in queue
   - Verify playback jumps
   - Verify highlighting updates

**Expected outcome:**
- All features work correctly
- No TypeScript errors
- Smooth loading transitions
- Loop state persists across refreshes
- Keyboard shortcuts work
