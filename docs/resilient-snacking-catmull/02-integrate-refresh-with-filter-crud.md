---
task: 02-integrate-refresh-with-filter-crud
status: pending
depends:
  - 01-create-refresh-function
files:
  - path: src/music_minion/domain/playlists/filters.py
    action: modify
---

# Integrate Refresh with Filter CRUD Operations

## Context
When filters are added, updated, or removed, the materialized track list must be refreshed to reflect the new filter criteria.

## Files to Modify/Create
- src/music_minion/domain/playlists/filters.py (modify)

## Implementation Details

Modify these functions to call `refresh_smart_playlist_tracks()` at the end:

### 1. `add_filter()` function
After the INSERT and before returning:
```python
def add_filter(...) -> int:
    # ... existing code ...
    conn.commit()
    filter_id = cursor.lastrowid

    # Refresh materialized tracks
    refresh_smart_playlist_tracks(playlist_id)

    return filter_id
```

### 2. `update_filter()` function
After the UPDATE and before returning:
```python
def update_filter(...) -> bool:
    # ... existing code ...
    conn.commit()

    # Get playlist_id for the filter being updated
    cursor = conn.execute("SELECT playlist_id FROM playlist_filters WHERE id = ?", (filter_id,))
    row = cursor.fetchone()
    if row:
        refresh_smart_playlist_tracks(row["playlist_id"])

    return True
```

### 3. `remove_filter()` function
After the DELETE and before returning:
```python
def remove_filter(...) -> bool:
    # First get playlist_id before deleting
    cursor = conn.execute("SELECT playlist_id FROM playlist_filters WHERE id = ?", (filter_id,))
    row = cursor.fetchone()
    playlist_id = row["playlist_id"] if row else None

    # ... existing delete code ...
    conn.commit()

    # Refresh materialized tracks
    if playlist_id:
        refresh_smart_playlist_tracks(playlist_id)

    return True
```

## Verification
```bash
# Start web app and test in browser
uv run music-minion --web

# 1. Create a smart playlist
# 2. Add a filter (e.g., genre = "dubstep")
# 3. Check sidebar - should show track count
# 4. Modify filter value
# 5. Verify track count updates
```
