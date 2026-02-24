---
task: 01-refactor-playlist-creation
status: done
depends: []
files:
  - path: web/backend/routers/soundcloud.py
    action: modify
---

# Refactor create_playlist_from_matches to Use Single Connection

## Context
The `create_playlist_from_matches` endpoint causes "database is locked" errors because it mixes the FastAPI-injected `db` connection with CRUD functions that open their own connections. This creates multiple simultaneous connections competing for write locks, causing timeout failures during SoundCloud playlist imports.

## Files to Modify/Create
- web/backend/routers/soundcloud.py (modify lines ~554-591)

## Implementation Details

### Problem
Current code mixes connection sources:
```python
existing = get_playlist_by_name(request.playlist_name)  # Opens own connection
# ...
playlist_id = crud_create_playlist(request.playlist_name, "manual")  # Opens own connection
db.execute("UPDATE playlists SET soundcloud_playlist_id...")  # Uses injected db
for match in valid_matches:
    add_track_to_playlist(playlist_id, match.local_track_id)  # Opens MORE connections
    db.execute("UPDATE tracks SET soundcloud_id...")  # Uses injected db
db.connection.commit()
```

### Solution
Replace with direct SQL using single injected `db` connection:

```python
# Check for duplicate playlist name using injected connection
# (replaces get_playlist_by_name() which opens its own connection)
cursor = db.execute(
    "SELECT id FROM playlists WHERE name = ? AND library = ?",
    (request.playlist_name, "local")
)
if cursor.fetchone():
    raise HTTPException(status_code=409, detail="Playlist name already exists")

try:
    # Create playlist using injected connection
    # Note: Using direct SQL instead of crud_create_playlist() to:
    # 1. Avoid opening multiple connections (fixes database lock error)
    # 2. Skip SoundCloud sync trigger (we're importing FROM SoundCloud, not TO it)
    cursor = db.execute(
        "INSERT INTO playlists (name, type, library) VALUES (?, ?, ?)",
        (request.playlist_name, "manual", "local")
    )
    playlist_id = cursor.lastrowid

    # Link to SoundCloud playlist ID
    db.execute(
        "UPDATE playlists SET soundcloud_playlist_id = ? WHERE id = ?",
        (request.sc_playlist_id, playlist_id)
    )

    # Batch insert playlist_tracks (no need for duplicate check - new playlist)
    playlist_tracks = [
        (playlist_id, m.local_track_id, idx + 1)
        for idx, m in enumerate(valid_matches)
    ]
    db.executemany(
        "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
        playlist_tracks
    )

    # Batch update tracks with soundcloud_id
    track_updates = [
        (m.sc_track_id, m.local_track_id)
        for m in valid_matches if m.sc_track_id
    ]
    if track_updates:
        db.executemany(
            "UPDATE tracks SET soundcloud_id = ? WHERE id = ?",
            track_updates
        )

    # Update track count
    db.execute(
        "UPDATE playlists SET track_count = ? WHERE id = ?",
        (len(valid_matches), playlist_id)
    )

    db.connection.commit()

    return ScCreatePlaylistResponse(
        playlist_id=playlist_id,
        track_count=len(valid_matches),
    )

except sqlite3.IntegrityError as e:
    db.connection.rollback()
    if "UNIQUE constraint" in str(e):
        raise HTTPException(status_code=409, detail="Playlist name already exists")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    db.connection.rollback()
    logger.exception("Error creating playlist from matches")
    raise HTTPException(status_code=500, detail=f"Failed to create playlist: {e}")
```

### Key Changes
1. Replace `get_playlist_by_name()` call with inline SQL (avoid opening separate connection)
2. Remove calls to `crud_create_playlist()` and `add_track_to_playlist()`
3. Use direct SQL with injected `db` connection throughout
4. Explicitly set `library='local'` in INSERT (imported playlists contain local tracks)
5. Use `executemany()` for batch operations (faster than loop)
6. Add `db.connection.rollback()` in error handlers
7. Add `import sqlite3` if not already present (for IntegrityError)

## Verification
1. Start music-minion with web mode: `uv run music-minion --web`
2. Open web UI: http://localhost:5173
3. Navigate to Settings → SoundCloud Import
4. Select a SoundCloud playlist with 20+ tracks
5. Complete the import wizard - should succeed without "database is locked"
6. Verify playlist created with correct track count
7. Check tracks have soundcloud_id populated in database
