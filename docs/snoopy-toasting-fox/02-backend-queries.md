---
task: 02-backend-queries
status: done
depends: [01-database-migration]
files:
  - path: web/backend/queries/buckets.py
    action: modify
---

# Backend Queries: Link/Unlink and Sync Functions

## Context
Core query layer for bucket-playlist linking. These functions handle the database operations for linking buckets, syncing tracks to linked playlists, and modifying existing assign/unassign behavior.

## Files to Modify/Create
- web/backend/queries/buckets.py (modify)

## Implementation Details

### New functions to add:

```python
def link_bucket_to_playlist(bucket_id: str, playlist_id: int) -> bool:
    """Link bucket to playlist. Returns False if bucket not found."""
    # INSERT OR REPLACE into bucket_playlist_links

def unlink_bucket(bucket_id: str) -> bool:
    """Remove playlist link from bucket."""
    # DELETE from bucket_playlist_links WHERE bucket_id = ?

def get_bucket_link(bucket_id: str) -> int | None:
    """Get linked playlist_id for bucket, or None if unlinked."""

def sync_track_to_linked_playlist(bucket_id: str, track_id: int) -> bool:
    """Add track to bucket's linked playlist (if linked). Called on bucket assignment."""
    # 1. Get linked playlist_id from bucket_playlist_links
    # 2. If linked, INSERT into playlist_tracks (if not already present)

def unsync_track_from_linked_playlist(bucket_id: str, track_id: int) -> bool:
    """Remove track from bucket's linked playlist (if linked). Called on bucket unassignment."""
    # 1. Get linked playlist_id from bucket_playlist_links
    # 2. If linked, DELETE from playlist_tracks
```

### Modify existing `assign_track_to_bucket`:

**REMOVE** the entire block that removes track from other buckets (lines ~533-562 in current code):
```python
# REMOVE THIS ENTIRE BLOCK:
# Check if track is in another bucket in this session
other_bucket_cursor = conn.execute(
    """
    SELECT bt.bucket_id, b.emoji_id
    FROM bucket_tracks bt
    JOIN buckets b ON bt.bucket_id = b.id
    WHERE b.session_id = ? AND bt.track_id = ?
    """,
    (session_id, track_id),
)
other_bucket = other_bucket_cursor.fetchone()

if other_bucket:
    # Remove from other bucket
    conn.execute(
        """
        DELETE FROM bucket_tracks
        WHERE bucket_id = ? AND track_id = ?
        """,
        (other_bucket["bucket_id"], track_id),
    )

    # Remove other bucket's emoji from track
    if other_bucket["emoji_id"]:
        remove_emoji_from_track_mutation(
            track_id,
            other_bucket["emoji_id"],
            conn,
            source_id=other_bucket["bucket_id"],
            force=True,
        )
```

**ADD** sync call after successful assignment:
```python
sync_track_to_linked_playlist(bucket_id, track_id)
```

### Modify `apply_session` to deduplicate multi-bucket tracks:

Add deduplication when building ordered_track_ids (first-bucket-wins):
```python
# Deduplicate: track appears at position of first bucket it's in
seen = set()
ordered_track_ids = []
for row in bucket_tracks_cursor.fetchall():
    if row["track_id"] not in seen:
        ordered_track_ids.append(row["track_id"])
        seen.add(row["track_id"])
```

### Modify existing `unassign_track`:

**ADD** sync removal call:
```python
unsync_track_from_linked_playlist(bucket_id, track_id)
```

## Verification

1. Write unit tests for new functions in `web/backend/tests/test_bucket_queries.py` (if exists) or add inline tests
2. Test link/unlink:
   ```python
   # In Python REPL or test
   link_bucket_to_playlist("bucket-uuid", 123)
   assert get_bucket_link("bucket-uuid") == 123
   unlink_bucket("bucket-uuid")
   assert get_bucket_link("bucket-uuid") is None
   ```
3. Test sync functions manually with a linked bucket and verify playlist_tracks table
