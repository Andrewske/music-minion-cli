---
task: 02-config-cache-playlist-id
status: pending
depends: [01-database-migration]
files:
  - path: src/music_minion/core/config.py
    action: modify
---

# Cache "All" Playlist ID in Configuration

## Context
Add a cached lookup for the "All" playlist ID to avoid repeated database queries. Saves ~5-10ms per comparison operation by querying once on first access and caching globally.

## Files to Modify/Create
- src/music_minion/core/config.py (modify)

## Implementation Details

Add to config module:

```python
# Cache "All" playlist ID on startup to avoid repeated lookups
ALL_PLAYLIST_ID: Optional[int] = None

def get_all_playlist_id() -> int:
    """Get cached All playlist ID, query once on first access."""
    global ALL_PLAYLIST_ID
    if ALL_PLAYLIST_ID is None:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT id FROM playlists WHERE name = 'All' LIMIT 1")
            row = cursor.fetchone()
            if not row:
                raise ValueError("All playlist not found - create a smart playlist named 'All' with no filters")
            ALL_PLAYLIST_ID = row['id']
    return ALL_PLAYLIST_ID
```

**Why:** This eliminates the repeated `SELECT id FROM playlists WHERE name='All'` query that would otherwise run on every comparison operation.

## Verification

Test that function works:
```bash
uv run python -c "
from music_minion.core.config import get_all_playlist_id

# First call queries database
all_id = get_all_playlist_id()
print(f'✅ All playlist ID: {all_id}')

# Second call uses cache (verify no DB query)
all_id_2 = get_all_playlist_id()
assert all_id == all_id_2, 'Cache broken!'
print('✅ Cache working correctly')
"
```
