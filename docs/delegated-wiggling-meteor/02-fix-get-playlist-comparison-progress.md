---
task: 02-fix-get-playlist-comparison-progress
status: done
depends:
  - 01-fix-get-next-playlist-pair
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Fix get_playlist_comparison_progress() for Smart Playlists

## Context
`get_playlist_comparison_progress()` also directly queries `playlist_tracks` table (line 400), causing it to return 0 tracks for smart playlists. Uses the same fix pattern.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

Modify `get_playlist_comparison_progress()` (lines 384-426):

1. **Add import if not already present:**
```python
from music_minion.domain.playlists.crud import get_playlist_track_count
```

2. **Replace track count query (lines 399-403):**
```python
# Before:
cursor = conn.execute(
    "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
    (playlist_id,),
)
track_count = cursor.fetchone()["count"]

# After:
track_count = get_playlist_track_count(playlist_id)
```

This uses the existing abstraction that handles both manual and smart playlists.

## Verification
```bash
uv run pytest src/music_minion/domain/rating/ -v
```
