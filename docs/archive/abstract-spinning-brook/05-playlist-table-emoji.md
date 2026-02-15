---
task: 05-playlist-table-emoji
depends: []
files:
  - path: web/frontend/src/components/PlaylistTracksTable.tsx
    action: modify
  - path: web/frontend/src/types.ts
    action: modify
  - path: web/backend/routers/playlists.py
    action: modify
---

# Add Emoji Tagging to PlaylistTracksTable

## Context
PlaylistTracksTable shows all tracks in a playlist with sorting. Adding emoji column lets users organize playlist tracks with tags.

## Files to Modify/Create
- web/frontend/src/components/PlaylistTracksTable.tsx (modify)
- web/frontend/src/types.ts (modify) - add emojis to PlaylistTrackEntry
- web/backend/routers/playlists.py (modify) - include emojis in response

## Implementation Details

### Backend (playlists.py)
Ensure `/api/playlists/{id}/tracks` returns `emojis` field for each track.

### Types (types.ts)
Add emojis field to PlaylistTrackEntry:
```typescript
interface PlaylistTrackEntry {
  // existing fields...
  emojis?: string[];
}
```

### Frontend (PlaylistTracksTable.tsx)
Add new column after Title:

```tsx
// Header (after Title column)
<th className="text-left py-3 px-2 text-slate-400 font-medium">Emojis</th>

// Cell (after title cell)
<td className="py-3 px-2">
  <EmojiTrackActions track={track} onUpdate={handleUpdate} compact />
</td>
```

**State management:**
- Need to update track in local sorted array on emoji change
- Or invalidate the playlist tracks query

## Verification
1. Navigate to `/playlist-builder/{playlistId}`
2. Scroll to All Tracks table
3. Verify emoji column appears
4. Add/remove emojis from table rows
5. Confirm changes persist after page refresh
