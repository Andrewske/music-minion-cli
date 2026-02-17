---
task: 03-frontend-api-functions
status: pending
depends: [02-backend-skip-endpoints]
files:
  - path: web/frontend/src/api/playlists.ts
    action: modify
---

# Frontend: Add Skip API Functions

## Context
The frontend needs API client functions to call the new skip endpoints. These will be used by the useSmartPlaylistEditor hook.

## Files to Modify/Create
- web/frontend/src/api/playlists.ts (modify)

## Implementation Details
Add three functions to the playlists API module:

```typescript
export async function skipSmartPlaylistTrack(
  playlistId: number,
  trackId: number
): Promise<void> {
  const response = await fetch(`/api/playlists/${playlistId}/skip/${trackId}`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to skip track');
}

export async function unskipSmartPlaylistTrack(
  playlistId: number,
  trackId: number
): Promise<void> {
  const response = await fetch(`/api/playlists/${playlistId}/skip/${trackId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to unskip track');
}

export async function getSmartPlaylistSkippedTracks(
  playlistId: number
): Promise<Track[]> {
  const response = await fetch(`/api/playlists/${playlistId}/skipped`);
  if (!response.ok) throw new Error('Failed to fetch skipped tracks');
  const data = await response.json();
  return data.skipped;
}
```

Follow existing patterns in the file for error handling and response parsing.

## Verification
1. Import functions in browser console or test file
2. Call each function against a test smart playlist
3. Verify network requests go to correct endpoints with correct methods
