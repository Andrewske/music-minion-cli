---
task: 05-playlist-sync
status: pending
depends:
  - 04-frontend-import-wizard
files:
  - path: web/frontend/src/routes/playlists.$playlistId.tsx
    action: modify
  - path: web/backend/routers/playlists.py
    action: modify
  - path: src/music_minion/domain/library/providers/soundcloud/api.py
    action: modify
---

# Playlist Sync: Reorder SoundCloud from Local

## Context
Separate feature from import wizard. When a local playlist is linked to a SoundCloud playlist (via import), show a "Sync to SoundCloud" button on the playlist page that reorders the SoundCloud playlist to match the local track order.

## Files to Modify/Create
- `web/frontend/src/routes/playlists.$playlistId.tsx` (or equivalent playlist detail route) (modify)
- `web/backend/routers/playlists.py` (modify)
- `src/music_minion/domain/library/providers/soundcloud/api.py` (modify - add reorder function)

## Implementation Details

### Backend: Reorder Function (api.py)

Add to SoundCloud provider:

```python
def reorder_playlist(
    state: ProviderState,
    playlist_id: str,
    track_ids: list[str]
) -> tuple[ProviderState, bool, str | None]:
    """Reorder a SoundCloud playlist.

    Uses PUT to replace the entire track list with new order.
    Returns: (state, success, error_message)
    """
```

**Implementation:** Use same PUT pattern as `add_track_to_playlist()` - format track URNs and PUT the full list.

### Backend: Sync Endpoint (playlists.py)

```python
@router.post("/{playlist_id}/sync-to-soundcloud")
async def sync_playlist_to_soundcloud(playlist_id: int):
    """Sync local playlist order to linked SoundCloud playlist.

    1. Get local playlist with tracks (in order)
    2. Get linked SC playlist ID from database
    3. Map local tracks to SC track IDs
    4. Call reorder_playlist with new order
    """
```

**Requires:**
- Local playlist has `soundcloud_playlist_id` set (from import)
- Local tracks have `soundcloud_id` set

### Frontend: Sync Button

On the playlist detail page, conditionally show sync button:

```tsx
{playlist.soundcloudPlaylistId && (
  <button
    onClick={handleSyncToSoundCloud}
    disabled={isSyncing}
  >
    {isSyncing ? 'Syncing...' : 'Sync to SoundCloud'}
  </button>
)}
```

**UX:**
- Show loading state during sync
- Toast success/error message
- Disable button while syncing

### Database Consideration

Ensure `playlists` table has `soundcloud_playlist_id` column. This should be set during `create-playlist-from-matches` endpoint (Task 02).

## Verification

1. Import a SoundCloud playlist (creates local playlist)
2. Reorder tracks in local playlist (drag/drop or however reordering works)
3. Navigate to playlist detail page
4. "Sync to SoundCloud" button should be visible
5. Click button → loading state → success toast
6. Check SoundCloud: playlist order should match local order
