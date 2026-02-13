# Extend Radio API with Emoji Support

## Files to Modify
- `web/backend/routers/radio.py` (modify)

## Implementation Details

### Update `TrackResponse` Schema

Find the `TrackResponse` class and add the `emojis` field:

```python
class TrackResponse(BaseModel):
    """Track representation for API responses."""
    id: int
    title: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    duration: Optional[float]
    local_path: Optional[str]
    emojis: list[str] = []  # NEW: List of emoji unicode strings
```

### Add Batch Emoji Fetching Helper

Add this helper function to avoid N+1 queries when fetching multiple tracks:

```python
def get_emojis_for_tracks_batch(track_ids: list[int], db_conn) -> dict[int, list[str]]:
    """Batch fetch emojis for multiple tracks. Returns dict mapping track_id -> emoji list."""
    if not track_ids:
        return {}

    placeholders = ','.join('?' * len(track_ids))
    cursor = db_conn.execute(
        f"SELECT track_id, emoji_id FROM track_emojis WHERE track_id IN ({placeholders}) ORDER BY track_id, added_at ASC",
        track_ids
    )

    result = {}
    for row in cursor.fetchall():
        track_id = row['track_id']
        emoji_id = row['emoji_id']
        if track_id not in result:
            result[track_id] = []
        result[track_id].append(emoji_id)

    return result
```

### Update `_track_to_response()` Helper

Find the `_track_to_response()` function and add emoji fetching logic:

```python
def _track_to_response(track, db_conn) -> TrackResponse:
    """Convert Track to TrackResponse with emojis."""
    # Fetch emojis for this track
    cursor = db_conn.execute(
        "SELECT emoji_id FROM track_emojis WHERE track_id = ? ORDER BY added_at ASC",
        (track.id,)
    )
    emojis = [row["emoji_id"] for row in cursor.fetchall()]

    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        duration=track.duration,
        local_path=track.local_path,
        emojis=emojis
    )
```

**For list endpoints (playlists, search results, etc.):** Use `get_emojis_for_tracks_batch()` instead:

```python
# Example: Playlist tracks endpoint
tracks = fetch_playlist_tracks(playlist_id)  # List of Track objects
track_ids = [t.id for t in tracks]
emojis_map = get_emojis_for_tracks_batch(track_ids, db_conn)

track_responses = [
    TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        duration=track.duration,
        local_path=track.local_path,
        emojis=emojis_map.get(track.id, [])
    )
    for track in tracks
]
```

**IMPORTANT:** If `_track_to_response()` doesn't exist, locate where `TrackResponse` objects are created (likely in `get_now_playing()` or similar endpoints) and add the emoji query there.

## Acceptance Criteria
- [ ] Backend runs without errors
- [ ] Test now-playing with a track that has emojis:
  1. Use emoji API to add emoji to a track:
     ```bash
     # Get now-playing track ID
     TRACK_ID=$(curl -s http://localhost:8642/api/radio/now-playing | jq '.track.id')

     # Add emoji
     curl -X POST http://localhost:8642/api/emojis/tracks/$TRACK_ID/emojis \
       -H "Content-Type: application/json" \
       -d '{"emoji_unicode": "🔥"}'

     # Verify now-playing includes emoji
     curl http://localhost:8642/api/radio/now-playing | jq '.track.emojis'
     # Should return ["🔥"]
     ```
- [ ] Empty emojis array for tracks without emojis (not null, not undefined)
- [ ] Emojis are ordered by `added_at ASC` (chronological order)

## Dependencies
- Task 01 (database migration)
- Task 02 (emoji router) - for testing
