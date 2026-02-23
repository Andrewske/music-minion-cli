---
task: 01-backend-track-search
status: done
depends: []
files:
  - path: web/backend/routers/tracks.py
    action: modify
  - path: src/music_minion/domain/library/deduplication.py
    action: reference
---

# Backend: Track Search Endpoint

## Context
Provides a search endpoint for the frontend to find local tracks when fixing low-confidence matches. This endpoint powers the autocomplete component in the import wizard.

## Files to Modify/Create
- `web/backend/routers/tracks.py` (modify)
- `src/music_minion/domain/library/deduplication.py` (reference for TF-IDF pattern)

## Implementation Details

Add `GET /api/tracks/search?q={query}&limit=20` endpoint:

```python
@router.get("/search")
async def search_tracks(q: str, limit: int = 20, db=Depends(get_db)):
    """Search local tracks for autocomplete.

    Uses simple LIKE query (matches existing codebase pattern).
    Returns: [{id, title, artist, album}]
    """
    query = f"%{q}%"
    cursor = db.execute("""
        SELECT id, title, artist, album
        FROM tracks
        WHERE (title LIKE ? COLLATE NOCASE OR artist LIKE ? COLLATE NOCASE)
          AND local_path IS NOT NULL
        LIMIT ?
    """, (query, query, limit))
    return [dict(row) for row in cursor.fetchall()]
```

**Implementation approach:**
1. Simple LIKE query with COLLATE NOCASE for case-insensitive matching
2. Only search tracks with `local_path IS NOT NULL` (true local files)
3. Return track metadata (id, title, artist, album)

**Indexing:** Ensure index exists for performance:
```sql
CREATE INDEX IF NOT EXISTS idx_tracks_title_artist ON tracks(title, artist);
```

**Pattern reference:** `filter_search_tracks()` in `state_selectors.py:62` uses same substring matching pattern.

## Verification

```bash
# Start web backend
music-minion --web

# Test search endpoint
curl "http://localhost:8642/api/tracks/search?q=artist%20name&limit=10"

# Expected: JSON array of matching tracks with id, title, artist, album
```
