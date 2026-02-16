---
task: 04-queue-and-context
status: done
depends: [03-player-components]
files:
  - path: web/frontend/src/components/TrackCard.tsx
    action: modify
  - path: web/frontend/src/components/playlist-builder/
    action: modify
  - path: web/frontend/src/components/ComparisonView.tsx
    action: modify
---

# Queue & Context

## Context
Wires up track clicks throughout the app to trigger playback. When you click a track anywhere, it should replace the queue with the appropriate context (playlist, builder, etc.) and start playing. Shuffle is handled entirely by the backend.

## Files to Modify/Create
- `web/frontend/src/components/TrackCard.tsx` (modify)
- `web/frontend/src/components/playlist-builder/*.tsx` (modify relevant files)
- `web/frontend/src/components/ComparisonView.tsx` (modify)
- `web/frontend/src/stores/playerStore.ts` (modify - add shuffle logic)

## Implementation Details

### 1. Context-aware queue initialization:

The `play()` action accepts a context that determines how to build the queue:

```typescript
// In playerStore.ts
async play(track: Track, context: PlayContext) {
  const { shuffleEnabled, thisDeviceId, activeDeviceId } = get()

  // Show loading state while waiting for backend
  set({ isLoading: true, playbackError: null })

  try {
    // Call backend to resolve context to queue (shuffle handled server-side)
    const response = await fetch('/api/player/play', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trackId: track.id,
        context: { ...context, shuffle: shuffleEnabled },
        activeDeviceId: activeDeviceId ?? thisDeviceId
      })
    })

    if (!response.ok) {
      throw new Error(`Play failed: ${response.statusText}`)
    }

    // Store context for shuffle toggle re-fetch
    // Actual playback state comes via WebSocket broadcast - no optimistic update
    set({ currentContext: context, isLoading: false })
  } catch (error) {
    set({ isLoading: false, playbackError: error.message })
  }
}
```

**Context types:**
```typescript
type PlayContext =
  | { type: 'playlist'; playlistId: number; startIndex: number }
  | { type: 'track' }  // Single track, no queue
  | { type: 'builder'; builderId: number; startIndex: number }
  | { type: 'comparison'; trackIds: number[]; startIndex: number }
  | { type: 'search'; query: string; startIndex: number }
```

### 2. Shuffle toggle (backend-driven):

```typescript
// In playerStore.ts
interface PlayerState {
  shuffleEnabled: boolean  // preference, persisted to localStorage
  currentContext: PlayContext | null  // remember what we're playing
}

toggleShuffle() {
  const { shuffleEnabled, currentContext, currentTrack } = get()
  const newShuffleEnabled = !shuffleEnabled

  // Persist preference
  localStorage.setItem('player:shuffle', String(newShuffleEnabled))
  set({ shuffleEnabled: newShuffleEnabled })

  // Re-fetch queue with new shuffle setting
  // NOTE: This resets position to 0 - known v1 limitation
  // Future: Add /api/player/toggle-shuffle endpoint to reorder without interruption
  if (currentContext && currentTrack) {
    fetch('/api/player/play', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trackId: currentTrack.id,
        context: { ...currentContext, shuffle: newShuffleEnabled }
      })
    })
    // State will be updated via WebSocket broadcast
  }
}
```

### 3. Wire up TrackCard.tsx:

Add click handler that triggers play with context.

```typescript
interface TrackCardProps {
  track: Track
  context?: PlayContext  // Passed by parent component
  // ... other props
}

export function TrackCard({ track, context, ...props }: TrackCardProps) {
  const { play } = usePlayer()

  const handleClick = () => {
    play(track, context ?? { type: 'track' })
  }

  return (
    <div onClick={handleClick} className="cursor-pointer ...">
      {/* existing content */}
    </div>
  )
}
```

### 4. Wire up playlist views:

When rendering tracks in a playlist, pass the playlist context:

```typescript
// In playlist view component
{playlist.tracks.map((track, index) => (
  <TrackCard
    key={track.id}
    track={track}
    context={{ type: 'playlist', playlistId: playlist.id, startIndex: index }}
  />
))}
```

### 5. Wire up playlist builder:

```typescript
// In ObsidianMinimalBuilder or similar
{builderTracks.map((track, index) => (
  <TrackCard
    key={track.id}
    track={track}
    context={{ type: 'builder', builderId: builderId, startIndex: index }}
  />
))}
```

### 6. Wire up ComparisonView:

```typescript
// Comparison tracks
const trackIds = comparisonTracks.map(t => t.id)
{comparisonTracks.map((track, index) => (
  <TrackCard
    key={track.id}
    track={track}
    context={{ type: 'comparison', trackIds, startIndex: index }}
  />
))}
```

### 7. Shuffle toggle in PlayerBar:

Already implemented in `03-player-components.md` - the shuffle button calls `toggleShuffle()` which re-fetches the queue from the backend with the new shuffle preference.

## Verification

1. Click a track in a playlist → verify queue shows playlist tracks starting from clicked track
2. Click a track in builder → verify queue shows builder tracks
3. Toggle shuffle off → verify backend returns sequential queue
4. Toggle shuffle on → verify backend returns shuffled queue
5. Navigate between pages, click track elsewhere → verify queue replaces completely
6. Verify position interpolation works (progress bar updates smoothly)
