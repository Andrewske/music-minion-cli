---
task: 02-extend-builder-hook
status: pending
depends: []
files:
  - path: web/frontend/src/hooks/useBuilderSession.ts
    action: modify
---

# Extend useBuilderSession Hook

## Context
Currently there are two separate hooks: `useBuilderSession` for manual playlists and `useSmartPlaylistEditor` for smart playlists. Extend the existing hook to handle both playlist types, enabling a unified PlaylistBuilder component.

## Files to Modify/Create
- `web/frontend/src/hooks/useBuilderSession.ts` (modify)

## Implementation Details

### Add playlistType Parameter
```typescript
function useBuilderSession(playlistId: number | null, playlistType: 'manual' | 'smart' = 'manual')
```

### Conditional Data Fetching
- **Manual**: Keep existing candidate fetching with pagination from builder API
- **Smart**: Fetch filtered tracks from `/api/playlists/{id}/tracks` (no pagination, all at once)

### Smart Playlist Mutations (merge from useSmartPlaylistEditor)
- `skipTrack`: Use `/api/playlists/{id}/skip/{trackId}` endpoint for smart playlists
- `unskipTrack`: Use `/api/playlists/{id}/skip/{trackId}` DELETE endpoint
- `skippedTracks` query: Fetch from `/api/playlists/{id}/skipped`

### Session Handling
- **Manual**: Require session (return `needsSession: true` when no session)
- **Smart**: No session needed (return `needsSession: false` always)

### Return Type Extension
```typescript
interface UseBuilderSessionReturn {
  // Existing fields...

  // Smart playlist additions
  unskipTrack?: UseMutationResult;
  skippedTracks?: Track[];
  needsSession: boolean;

  // Tracks (unified name for candidates/filtered tracks)
  tracks: Track[];
}
```

### Query Key Differentiation
- Manual candidates: `['builder-candidates', playlistId, ...]`
- Smart tracks: `['playlist-tracks', playlistId, ...]`
- Smart skipped: `['smart-playlist-skipped', playlistId]`

## Verification
1. Hook compiles without TypeScript errors
2. Manual playlist flow unchanged (session required, candidates fetched)
3. Smart playlist returns tracks from filter API
4. Skip mutations use correct endpoints per playlist type
