# Playlist Pinning Design

Pin playlists to the top of the sidebar list with drag-to-reorder support.

## Requirements

- Pin playlists to top of sidebar list
- Reorder pinned playlists via drag-and-drop
- Pin icon on hover to toggle pin status
- Pin icon always visible on pinned items
- Database-persisted (syncs across devices/sessions)

## Database Schema

**Migration v32:** Add `pin_order` column to playlists table.

```sql
ALTER TABLE playlists ADD COLUMN pin_order INTEGER DEFAULT NULL;
CREATE INDEX idx_playlists_pin_order ON playlists(pin_order);
```

- `NULL` = unpinned
- `1, 2, 3...` = pinned + ordered

**Query pattern:**
```sql
SELECT * FROM playlists
ORDER BY (pin_order IS NULL), pin_order, name
```

**CRUD functions:**
- `pin_playlist(playlist_id: int, position: int | None = None)` - Sets pin_order
- `unpin_playlist(playlist_id: int)` - Sets pin_order to NULL, reorders remaining
- `reorder_pinned_playlist(playlist_id: int, new_position: int)` - Moves pinned playlist

## Backend API

**Endpoints in `web/backend/routers/playlists.py`:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/playlists/{id}/pin` | Pin playlist to end |
| DELETE | `/api/playlists/{id}/pin` | Unpin playlist |
| PATCH | `/api/playlists/{id}/pin` | Reorder pinned playlist (body: `{"position": N}`) |

**Response schema update:**
- Add `pin_order: int | None` to playlist response

## Frontend

**Type update (`types/index.ts`):**
```typescript
interface Playlist {
  // ... existing
  pin_order: number | null;
}
```

**API functions (`api/playlists.ts`):**
- `pinPlaylist(id: number)`
- `unpinPlaylist(id: number)`
- `reorderPinnedPlaylist(id: number, position: number)`

**SidebarPlaylists.tsx:**
- Split into `pinned` and `unpinned` arrays
- Pinned section: drag-to-reorder via @dnd-kit
- Hover: show Pin/Unpin icon
- Pinned items: show small Pin icon next to name

## Files to Modify

**Backend:**
- `src/music_minion/core/database.py` - Migration v32
- `src/music_minion/domain/playlists/crud.py` - pin/unpin/reorder functions
- `web/backend/routers/playlists.py` - Pin endpoints

**Frontend:**
- `web/frontend/src/types/index.ts` - Playlist interface
- `web/frontend/src/api/playlists.ts` - Pin API functions
- `web/frontend/src/components/sidebar/SidebarPlaylists.tsx` - UI changes
