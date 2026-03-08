# Bucket-to-Playlist Linking

Link buckets in the playlist organizer to actual playlists for bidirectional sync.

## Summary

| Aspect | Decision |
|--------|----------|
| Link UI | During bucket creation + edit bucket popup |
| Sync timing | Immediate (add to bucket → add to playlist) |
| Inverse sync | On organizer load (compute bucket contents fresh) |
| Remove sync | Yes, remove from linked playlist too |
| Multi-bucket | Tracks can be in multiple buckets |
| Multi-display | Track shows in each bucket it belongs to |
| Remove UX | Click assigned bucket to toggle off |
| Unsorted | Back to main track list |
| Linked indicator | Playlist name in parentheses, bucket-colored |
| Playlist picker | Same library, exclude parent playlist |
| Create option | Yes, "+ Create new playlist" at top |
| Storage | New database table |
| Deleted playlist | Bucket becomes unlinked, keeps tracks locally |

## Database Changes

### New table: `bucket_playlist_links`

```sql
CREATE TABLE IF NOT EXISTS bucket_playlist_links (
    id TEXT PRIMARY KEY,
    bucket_id TEXT NOT NULL UNIQUE,  -- One link per bucket
    playlist_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bucket_id) REFERENCES buckets (id) ON DELETE CASCADE,
    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_bucket_playlist_links_bucket ON bucket_playlist_links(bucket_id);
CREATE INDEX IF NOT EXISTS idx_bucket_playlist_links_playlist ON bucket_playlist_links(playlist_id);
```

Note: `ON DELETE SET NULL` for playlist allows bucket to become unlinked when playlist is deleted.

### Schema change: `bucket_tracks` allows multiple buckets

Currently has `UNIQUE (bucket_id, track_id)` which allows a track in multiple buckets. No change needed.

**Verification needed**: Current `assignTrack` backend logic removes track from other buckets before adding. This needs to change.

## Backend Changes

### 1. New queries module additions (`web/backend/queries/buckets.py`)

```python
def link_bucket_to_playlist(bucket_id: str, playlist_id: int) -> bool:
    """Link bucket to playlist. Returns False if bucket not found."""

def unlink_bucket(bucket_id: str) -> bool:
    """Remove playlist link from bucket."""

def get_bucket_link(bucket_id: str) -> int | None:
    """Get linked playlist_id for bucket, or None if unlinked."""

def get_linked_tracks_for_bucket(bucket_id: str, parent_playlist_id: int) -> list[int]:
    """
    Get track IDs that should appear in bucket based on linked playlist.
    Returns intersection of (linked_playlist tracks) AND (parent_playlist tracks).
    """

def sync_track_to_linked_playlist(bucket_id: str, track_id: int) -> bool:
    """Add track to bucket's linked playlist (if linked). Called on bucket assignment."""

def unsync_track_from_linked_playlist(bucket_id: str, track_id: int) -> bool:
    """Remove track from bucket's linked playlist (if linked). Called on bucket unassignment."""
```

### 2. Modify `assign_track_to_bucket` (existing function)

Current behavior: Removes track from ALL other buckets before adding.
New behavior: Only add to target bucket (allow multi-bucket membership).

```python
# REMOVE this line from assign_track_to_bucket:
# conn.execute("DELETE FROM bucket_tracks WHERE track_id = ? AND bucket_id != ?", ...)

# ADD sync to linked playlist:
sync_track_to_linked_playlist(bucket_id, track_id)
```

### 3. Modify `unassign_track` (existing function)

Add sync removal:
```python
unsync_track_from_linked_playlist(bucket_id, track_id)
```

### 4. New API endpoints (`web/backend/routers/buckets.py`)

```python
class LinkBucketBody(BaseModel):
    playlist_id: int | None  # None to unlink

@router.post("/{bucket_id}/link")
async def link_bucket_endpoint(bucket_id: str, body: LinkBucketBody):
    """Link/unlink bucket to playlist."""

@router.get("/{bucket_id}/link")
async def get_bucket_link_endpoint(bucket_id: str) -> dict:
    """Get current link status for bucket."""
```

### 5. Modify session loading (`get_or_create_session`)

On session load/resume, compute bucket contents:
1. For each bucket with a linked playlist:
   - Get tracks in linked playlist that are ALSO in parent playlist
   - These tracks should appear in the bucket
2. Merge with existing bucket assignments (dedup)

## Frontend Changes

### 1. Update types (`web/frontend/src/api/buckets.ts`)

```typescript
export interface Bucket {
  id: string;
  name: string;
  emoji_id: string | null;
  position: number;
  track_ids: number[];
  linked_playlist_id: number | null;  // NEW
  linked_playlist_name: string | null;  // NEW (for display)
}

export interface LinkBucketBody {
  playlist_id: number | null;
}
```

### 2. New API functions (`web/frontend/src/api/buckets.ts`)

```typescript
export async function linkBucket(bucketId: string, playlistId: number | null): Promise<void>;
export async function getBucketLink(bucketId: string): Promise<{ playlist_id: number | null }>;
```

### 3. Update hook (`web/frontend/src/hooks/usePlaylistOrganizer.ts`)

- Add `linkBucket` mutation
- Update `assignTrack` optimistic update to NOT remove from other buckets
- Add loading state for linking

### 4. Update bucket edit popup

Current: Name + emoji
New: Name + emoji + playlist link selector

Components needed:
- Playlist dropdown/combobox (filter: same library, exclude parent)
- "+ Create new playlist" option at top
- Shows current link status

### 5. Update bucket header display

Current: `{emoji} {name} ({count})`
New: `{emoji} {name} ({count}) (Linked Playlist Name)` where playlist name uses bucket color

### 6. Update `assignTrackMutation` optimistic update

```typescript
// REMOVE: Remove track from other buckets
// const updatedBuckets = previousSession.buckets.map((bucket) => {
//   if (bucket.id === bucketId) { ... }
//   return { ...bucket, track_ids: bucket.track_ids.filter((id) => id !== trackId) };
// });

// NEW: Only add to target bucket, keep in others
const updatedBuckets = previousSession.buckets.map((bucket) => {
  if (bucket.id === bucketId && !bucket.track_ids.includes(trackId)) {
    return { ...bucket, track_ids: [...bucket.track_ids, trackId] };
  }
  return bucket;
});
```

### 7. Toggle behavior for bucket clicks

When clicking a bucket that already contains the current track:
- Call `unassignTrack` instead of `assignTrack`
- Update `assignCurrentTrackToBucket` to check membership first

## Implementation Order

1. **Database migration** - Add `bucket_playlist_links` table
2. **Backend queries** - Link/unlink functions, sync functions
3. **Backend API** - Link endpoints, modify assign/unassign
4. **Frontend types** - Update Bucket interface
5. **Frontend API** - Add link functions
6. **Frontend hook** - Update mutations for multi-bucket
7. **Bucket edit popup** - Add playlist selector
8. **Bucket header** - Show linked playlist name
9. **Toggle behavior** - Click to unassign if already in bucket
10. **Session loading** - Compute bucket contents from linked playlists

## Edge Cases

1. **Linked playlist deleted**: `ON DELETE SET NULL` in FK makes `linked_playlist_id` null. Bucket keeps local track assignments.

2. **Track removed from parent playlist**: On next organizer load, track won't appear in linked bucket (intersection logic filters it out).

3. **Track in multiple linked buckets**: Shows in all of them. Removing from one bucket only removes from that bucket's linked playlist.

4. **Creating new playlist from bucket**: Use existing playlist creation API, then link bucket to it.

## Files to Modify

**Backend:**
- `src/music_minion/core/database.py` - Migration for new table
- `web/backend/queries/buckets.py` - Link queries, modify assign/unassign
- `web/backend/routers/buckets.py` - Link endpoints, response models

**Frontend:**
- `web/frontend/src/api/buckets.ts` - Types, link API
- `web/frontend/src/hooks/usePlaylistOrganizer.ts` - Multi-bucket mutations, link mutation
- `web/frontend/src/pages/PlaylistOrganizer.tsx` - Toggle behavior
- `web/frontend/src/components/organizer/BucketList.tsx` - Linked indicator
- `web/frontend/src/components/organizer/BucketEditPopup.tsx` - Playlist selector (new or modify existing)
