# Frontend Types and API Client Updates

## Files to Modify/Create
- `web/frontend/src/types/index.ts` (modify)
- `web/frontend/src/api/playlists.ts` (modify)

## Implementation Details

### 1. Add Library Field to Playlist Interface

Update the `Playlist` interface in `types/index.ts` (around line 21-27):

```typescript
export interface Playlist {
  id: number;
  name: string;
  type: string;
  description?: string;
  track_count: number;
  library: string;  // ADD THIS LINE
}
```

### 2. Add Create Playlist Function

Add the following function to `api/playlists.ts` after existing imports:

```typescript
export async function createPlaylist(name: string, description: string = ''): Promise<Playlist> {
  const response = await fetch(`${API_BASE}/playlists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create playlist');
    } catch (e) {
      // If JSON parsing fails (e.g., HTML error page), use generic message
      throw new Error('Failed to create playlist');
    }
  }

  return response.json();
}
```

### Function Signature
- **name** (string, required): Playlist name
- **description** (string, optional): Playlist description
- **Returns**: Promise<Playlist> with full playlist data

### Error Handling
- Parses error response from backend
- Throws error with backend's `detail` message or generic fallback

## Acceptance Criteria
- [ ] `library` field added to Playlist interface
- [ ] `createPlaylist` function exported from playlists.ts
- [ ] Function accepts name and optional description
- [ ] Function returns typed Playlist object
- [ ] Error handling extracts detail from response
- [ ] TypeScript compilation succeeds

## Dependencies
- Task 03 (backend endpoint must exist for API client to call)
