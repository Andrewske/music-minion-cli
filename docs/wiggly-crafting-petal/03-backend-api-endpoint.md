# Backend - Add Create Playlist Endpoint

## Files to Modify/Create
- `web/backend/routers/playlists.py` (modify)
- `web/backend/schemas.py` (modify)

## Implementation Details

### 1. Add Pydantic Schema

Add to `web/backend/schemas.py` after existing schemas:

```python
class CreatePlaylistRequest(BaseModel):
    name: str
    description: str = ""
```

### 2. Add POST Endpoint

Add to `web/backend/routers/playlists.py` after the existing GET endpoint (after line 62):

```python
@router.post("/playlists")
async def create_playlist(request: CreatePlaylistRequest):
    """Create a new manual playlist."""
    try:
        from music_minion.domain.playlists.crud import create_playlist as create_playlist_fn

        # Create playlist (explicitly set library='local')
        playlist_id = create_playlist_fn(
            name=request.name,
            playlist_type="manual",
            description=request.description,
            library="local"
        )

        # Get created playlist data
        from music_minion.core.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, type, description, track_count, library FROM playlists WHERE id = ?",
                (playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Created playlist but failed to fetch")
            playlist = dict(row)

        return playlist
    except ValueError as e:
        # Handle duplicate name error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create playlist: {str(e)}")
```

### Validation Notes
The `create_playlist()` function in `crud.py` already validates name uniqueness, so duplicate names will raise a `ValueError` that gets caught and returned as a 400 error.

## Acceptance Criteria
- [ ] POST endpoint added at `/playlists`
- [ ] Accepts `name` (required) and `description` (optional) parameters
- [ ] Returns created playlist with all fields (id, name, type, description, track_count, library)
- [ ] Returns 400 for duplicate names
- [ ] Returns 500 for other errors with descriptive message

## Testing
```bash
# Test successful creation
curl -X POST http://localhost:8642/api/playlists \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Playlist", "description": "Testing"}'

# Test duplicate name (should return 400)
curl -X POST http://localhost:8642/api/playlists \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Playlist", "description": "Duplicate"}'
```

## Dependencies
None - backend changes are independent
