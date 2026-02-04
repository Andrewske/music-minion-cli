# Backend: Smart Filter Endpoints

## Files to Modify/Create
- `web/backend/routers/playlists.py` (modify)
- `web/backend/schemas.py` (modify)

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
    """Replace all filters for a smart playlist."""
    # 1. Verify playlist exists and is type='smart'
    # 2. Delete existing filters for playlist (DELETE FROM playlist_filters WHERE playlist_id = ?)
    # 3. Add new filters via add_filter() for each filter in list
    # 4. Return updated filters via get_playlist_filters()
```

### Domain Functions Available
From `src/music_minion/domain/playlists/filters.py`:
- `get_playlist_filters(playlist_id)` - returns list of filter dicts
- `add_filter(playlist_id, field, operator, value, conjunction)` - adds single filter
- `remove_filter(filter_id)` - removes single filter
- `validate_filter(field, operator, value)` - validates filter params

## Acceptance Criteria
- [ ] `GET /playlists/{id}/filters` returns filter list for smart playlist
- [ ] `GET /playlists/{id}/filters` returns empty list for playlist with no filters
- [ ] `PUT /playlists/{id}/filters` replaces all filters atomically
- [ ] `PUT /playlists/{id}/filters` validates each filter before applying
- [ ] Endpoints return 404 for non-existent playlist
- [ ] Endpoints return 400 for non-smart playlist

## Dependencies
None - this is the foundational backend work.
