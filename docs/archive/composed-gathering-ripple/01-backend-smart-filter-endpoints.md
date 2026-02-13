# Backend: Smart Filter Endpoints

## Files to Modify/Create
- `web/backend/routers/playlists.py` (modify)
- `web/backend/schemas.py` (modify)

## Review Decisions Applied
- **Track data**: Extend `/playlists/{id}/tracks` to return full track fields (album, genre, bpm, key_signature, year, elo_rating) for smart playlists
- **Sorting**: Add `sort_field` and `sort_direction` query params to tracks endpoint
- **Atomicity**: PUT filters must validate all filters first, then use single transaction for DELETE + INSERT

## Implementation Details

### Schemas (`web/backend/schemas.py`)

Add Pydantic models for filter input/output:

```python
class FilterInput(BaseModel):
    field: str
    operator: str
    value: str
    conjunction: str = "AND"

class FilterResponse(BaseModel):
    id: int
    field: str
    operator: str
    value: str
    conjunction: str
```

### Endpoints (`web/backend/routers/playlists.py`)

Add two endpoints for smart playlist filter management:

```python
@router.get("/playlists/{playlist_id}/filters")
async def get_smart_filters(playlist_id: int):
    """Get filters for a smart playlist."""
    # Call get_playlist_filters(playlist_id) from domain layer
    # Return list of {id, field, operator, value, conjunction}

@router.put("/playlists/{playlist_id}/filters")
async def update_smart_filters(playlist_id: int, filters: List[FilterInput]):
    """Replace all filters for a smart playlist (atomic operation)."""
    # 1. Verify playlist exists and is type='smart'
    # 2. Validate ALL filters first (call validate_filter() for each)
    #    - If any validation fails, return 400 immediately without modifying DB
    # 3. In single transaction:
    #    - DELETE FROM playlist_filters WHERE playlist_id = ?
    #    - INSERT all new filters via executemany()
    #    - Rollback on any failure
    # 4. Return updated filters via get_playlist_filters()
```

### Domain Functions Available
From `src/music_minion/domain/playlists/filters.py`:
- `get_playlist_filters(playlist_id)` - returns list of filter dicts
- `add_filter(playlist_id, field, operator, value, conjunction)` - adds single filter
- `remove_filter(filter_id)` - removes single filter
- `validate_filter(field, operator, value)` - validates filter params

### Extended Tracks Endpoint (modify existing)

Update `GET /playlists/{playlist_id}/tracks` for smart playlists:

```python
@router.get("/playlists/{playlist_id}/tracks")
async def get_playlist_tracks(
    playlist_id: int,
    sort_field: str = "artist",
    sort_direction: str = "asc"
):
    """Get tracks with full metadata for smart playlists."""
    # For smart playlists, return extended fields:
    # id, title, artist, album, genre, year, bpm, key_signature, elo_rating
    # Plus: rating, wins, losses, comparison_count (existing)
    # Apply sorting via ORDER BY clause
```

## Acceptance Criteria
- [ ] `GET /playlists/{id}/filters` returns filter list for smart playlist
- [ ] `GET /playlists/{id}/filters` returns empty list for playlist with no filters
- [ ] `PUT /playlists/{id}/filters` validates ALL filters before any DB writes
- [ ] `PUT /playlists/{id}/filters` uses single transaction (atomic replace)
- [ ] `GET /playlists/{id}/tracks` returns full track fields for smart playlists
- [ ] `GET /playlists/{id}/tracks` supports sort_field and sort_direction params
- [ ] Endpoints return 404 for non-existent playlist
- [ ] Endpoints return 400 for non-smart playlist (PUT only)

## Dependencies
None - this is the foundational backend work.
