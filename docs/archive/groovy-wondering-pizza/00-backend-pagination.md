---
task: 00-backend-pagination
status: done
depends: []
files:
  - path: web/backend/routers/playlists.py
    action: modify
  - path: web/frontend/src/api/playlists.ts
    action: modify
---

# Add Pagination to Smart Playlist Tracks Endpoint

## Context
To unify manual and smart playlist builders with consistent infinite query pattern, the smart playlist tracks endpoint needs pagination support matching the builder candidates endpoint.

## Files to Modify
- `web/backend/routers/playlists.py` (modify)
- `web/frontend/src/api/playlists.ts` (modify)

## Implementation Details

### Backend: Add Pagination Params
Update `/api/playlists/{id}/tracks` endpoint:

```python
@router.get("/{playlist_id}/tracks")
async def get_playlist_tracks(
    playlist_id: int,
    limit: int = 100,
    offset: int = 0,
    sort_field: str = "artist",
    sort_direction: str = "asc",
):
    # Existing filter logic...

    # Add pagination
    total = len(all_tracks)
    tracks = all_tracks[offset:offset + limit]

    return {
        "tracks": tracks,
        "total": total,
        "hasMore": offset + len(tracks) < total
    }
```

### Frontend: Update API Function
```typescript
export async function getSmartPlaylistTracks(
  playlistId: number,
  limit: number = 100,
  offset: number = 0,
  sortField: string = 'artist',
  sortDirection: string = 'asc'
): Promise<{ tracks: Track[]; total: number; hasMore: boolean }> {
  const response = await fetch(
    `${API_BASE}/playlists/${playlistId}/tracks?limit=${limit}&offset=${offset}&sort_field=${sortField}&sort_direction=${sortDirection}`
  );
  if (!response.ok) throw new Error('Failed to fetch tracks');
  return response.json();
}
```

## Verification
1. Endpoint returns paginated results with `total` and `hasMore`
2. Sorting works correctly with pagination
3. Existing smart playlist editor still works (backwards compatible with defaults)
