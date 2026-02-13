# Frontend Playlist Builder Page - Main UI

## Files to Create/Modify
- `web/frontend/src/pages/PlaylistBuilder.tsx` (new)
- `web/frontend/src/hooks/useIPCWebSocket.ts` (modify)
- `web/frontend/src/App.tsx` (modify - add route)

## Implementation Details

### 1. Main Page Component (`web/frontend/src/pages/PlaylistBuilder.tsx`)

Create full-featured playlist builder UI with:
- Playlist selection
- Filter panel
- Track player with loop
- Add/Skip buttons
- Stats display
- WebSocket integration for keyboard shortcuts

```typescript
import { useState, useEffect, useRef } from 'react';
import { useBuilderSession } from '../hooks/useBuilderSession';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { builderApi, Track } from '../api/builder';

export function PlaylistBuilder() {
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const {
    session,
    addTrack,
    skipTrack,
    filters,
    updateFilters,
    startSession,
    isAddingTrack,
    isSkippingTrack
  } = useBuilderSession(selectedPlaylistId);

  // Activate builder mode on mount, deactivate on unmount
  useEffect(() => {
    if (selectedPlaylistId) {
      builderApi.activateBuilderMode(selectedPlaylistId);

      return () => {
        builderApi.deactivateBuilderMode();
      };
    }
  }, [selectedPlaylistId]);

  // Fetch initial candidate after session starts
  useEffect(() => {
    if (session && !currentTrack) {
      builderApi.getNextCandidate(selectedPlaylistId!).then(setCurrentTrack);
    }
  }, [session, currentTrack, selectedPlaylistId]);

  // Handle keyboard shortcuts via WebSocket (useRef pattern)
  useIPCWebSocket({
    onBuilderAdd: () => {
      if (currentTrack && !isAddingTrack && !isSkippingTrack) {
        handleAdd();
      }
    },
    onBuilderSkip: () => {
      if (currentTrack && !isAddingTrack && !isSkippingTrack) {
        handleSkip();
      }
    }
  });

  // Auto-play current track on loop
  useEffect(() => {
    if (currentTrack && audioRef.current) {
      const audio = audioRef.current;
      audio.src = `/api/tracks/${currentTrack.id}/stream`;
      audio.loop = true;
      audio.play().catch(err => {
        console.error('Failed to play audio:', err);
        // Auto-skip on playback error
        setTimeout(() => skipTrack.mutate(currentTrack.id), 3000);
      });

      return () => {
        audio.pause();
        audio.src = '';
      };
    }
  }, [currentTrack?.id]);

  // Handle add track
  const handleAdd = async () => {
    if (!currentTrack || isAddingTrack || isSkippingTrack) return;

    const trackId = currentTrack.id;
    await addTrack.mutateAsync(trackId);

    // Fetch next candidate
    const nextTrack = await builderApi.getNextCandidate(selectedPlaylistId!, trackId);
    setCurrentTrack(nextTrack);
  };

  // Handle skip track
  const handleSkip = async () => {
    if (!currentTrack || isAddingTrack || isSkippingTrack) return;

    const trackId = currentTrack.id;
    await skipTrack.mutateAsync(trackId);

    // Fetch next candidate
    const nextTrack = await builderApi.getNextCandidate(selectedPlaylistId!, trackId);
    setCurrentTrack(nextTrack);
  };

  if (!selectedPlaylistId) {
    return <PlaylistSelection onSelect={setSelectedPlaylistId} />;
  }

  if (!session) {
    return (
      <div className="builder-setup">
        <h2>Start Building Playlist</h2>
        <button onClick={() => startSession.mutate(selectedPlaylistId)}>
          Start Session
        </button>
      </div>
    );
  }

  return (
    <div className="playlist-builder">
      <audio ref={audioRef} />

      <div className="builder-layout">
        {/* Left Panel: Filters */}
        <aside className="filter-panel">
          <h3>Filters</h3>
          <FilterPanel
            filters={filters || []}
            onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
          />
        </aside>

        {/* Center: Track Player */}
        <main className="track-player">
          {currentTrack ? (
            <>
              <TrackDisplay track={currentTrack} />

              <div className="controls">
                <button
                  onClick={handleAdd}
                  disabled={isAddingTrack || isSkippingTrack}
                  className="btn-add"
                >
                  {isAddingTrack ? 'Adding...' : 'Add to Playlist'}
                </button>
                <button
                  onClick={handleSkip}
                  disabled={isAddingTrack || isSkippingTrack}
                  className="btn-skip"
                >
                  {isSkippingTrack ? 'Skipping...' : 'Skip'}
                </button>
              </div>

              <StatsPanel stats={stats} />
            </>
          ) : (
            <div className="no-candidates">
              <h3>No more candidates</h3>
              <p>Adjust your filters or review skipped tracks</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// Supporting Components

function TrackDisplay({ track }: { track: Track }) {
  return (
    <div className="track-display">
      <h2>{track.title}</h2>
      <p className="artist">{track.artist}</p>
      {track.album && <p className="album">{track.album}</p>}
      <div className="metadata">
        {track.genre && <span className="genre">{track.genre}</span>}
        {track.year && <span className="year">{track.year}</span>}
        {track.bpm && <span className="bpm">{track.bpm} BPM</span>}
        {track.key_signature && <span className="key">{track.key_signature}</span>}
      </div>
    </div>
  );
}

function StatsPanel({ stats }: { stats: any }) {
  return (
    <div className="stats-panel">
      <h4>Session Stats</h4>
      <ul>
        <li>{stats?.candidatesRemaining || 0} candidates remaining</li>
        <li>Started: {new Date(stats?.startedAt).toLocaleString()}</li>
      </ul>
    </div>
  );
}

function FilterPanel({ filters, onUpdate }: { filters: any[]; onUpdate: (filters: any[]) => void }) {
  // TODO: Implement filter UI
  // - Genre dropdown
  // - BPM range
  // - Year range
  // - Key signature
  // Similar to smart playlist filter UI
  return <div>Filter Panel (TODO)</div>;
}

function PlaylistSelection({ onSelect }: { onSelect: (id: number) => void }) {
  // TODO: Fetch and display manual playlists
  // - List playlists
  // - Filter to manual only
  // - Create new playlist button
  return <div>Playlist Selection (TODO)</div>;
}
```

### 2. Update WebSocket Hook (`web/frontend/src/hooks/useIPCWebSocket.ts`)

Add builder message handlers with useRef pattern to prevent reconnections:

```typescript
export function useIPCWebSocket(handlers: {
  onBuilderAdd?: () => void;
  onBuilderSkip?: () => void;
  // ... existing handlers
}) {
  const handlersRef = useRef(handlers);

  // Update ref when handlers change (no reconnection)
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8765';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'builder:add') {
          handlersRef.current.onBuilderAdd?.();
        } else if (msg.type === 'builder:skip') {
          handlersRef.current.onBuilderSkip?.();
        }
        // ... existing message handling
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return () => {
      ws.close();
    };
  }, []); // Only connect once - no dependencies
}
```

### 3. Add Environment Variable (`web/frontend/.env.example`)

```bash
# WebSocket URL for IPC communication
VITE_WS_URL=ws://localhost:8765
```

### 3. Add Route (`web/frontend/src/App.tsx`)

```typescript
import { PlaylistBuilder } from './pages/PlaylistBuilder';

// In routes:
<Route path="/playlist-builder" element={<PlaylistBuilder />} />
```

## UI Layout

```
┌─────────────────────────────────────────────┐
│ Playlist Builder                             │
├─────────────┬───────────────────────────────┤
│             │                               │
│  Filters    │    Current Track              │
│             │    ┌─────────────────────┐   │
│  Genre: All │    │  Song Title          │   │
│  BPM: Any   │    │  Artist Name         │   │
│  Year: Any  │    │  Album • 2024        │   │
│  Key: Any   │    │  House • 128 BPM     │   │
│             │    └─────────────────────┘   │
│  [Clear]    │                               │
│             │    [Add to Playlist] [Skip]   │
│             │                               │
│             │    Stats:                     │
│             │    • 47 candidates            │
│             │    • Started: 2:30 PM         │
└─────────────┴───────────────────────────────┘
```

## Key Features

1. **Audio Playback**
   - Auto-play on track change
   - Loop enabled
   - Error handling with auto-skip

2. **Keyboard Shortcuts**
   - Listen for WebSocket messages
   - Trigger mutations on command

3. **Loading States**
   - Disable buttons during mutations
   - Show loading text

4. **Error Handling**
   - Toast notifications for errors
   - Graceful degradation

5. **Responsive Design**
   - Mobile-friendly layout
   - Touch-friendly buttons

## Acceptance Criteria

1. Page renders with playlist selection
2. Session starts and loads first candidate
3. Audio plays on loop
4. Add/Skip buttons work
5. Keyboard shortcuts trigger actions
6. Stats display correctly
7. "No candidates" state shown when empty
8. Filter panel updates trigger re-fetch
9. Route accessible at `/playlist-builder`
10. WebSocket integration functional

## Dependencies
- Task 05: Frontend API client
- Task 06: React Query hook

## Testing

Manual testing flow:
1. Navigate to `http://localhost:5173/playlist-builder`
2. Select a manual playlist
3. Click "Start Session"
4. Verify audio plays on loop
5. Click "Add" → Track advances to next
6. Click "Skip" → Track advances to next
7. Press keyboard shortcut → Same as button
8. Adjust filters → Candidate pool updates
9. Close browser, reopen → Session resumes

Integration tests:
```typescript
describe('PlaylistBuilder', () => {
  it('starts session and plays track', async () => {
    render(<PlaylistBuilder />);
    // Test implementation
  });

  it('responds to keyboard shortcuts', async () => {
    // Test WebSocket message triggers action
  });
});
```
