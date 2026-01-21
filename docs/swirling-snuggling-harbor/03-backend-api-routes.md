# Backend API Routes - Builder Endpoints

## Files to Create/Modify
- `web/backend/routers/builder.py` (new)
- `web/backend/main.py` (modify - add router registration)
- `web/backend/schemas.py` (modify - add Pydantic models)

## Implementation Details

### 1. Create FastAPI Router (`web/backend/routers/builder.py`)

Implement RESTful API endpoints for playlist builder operations.

#### Context Activation Endpoints
```python
@router.post("/activate/{playlist_id}")
async def activate_builder_mode(
    playlist_id: int,
    db: Session = Depends(get_db)
):
    """Activate builder mode for keyboard shortcuts.

    Updates AppContext.active_web_mode = 'builder'
    Updates AppContext.active_builder_playlist_id = playlist_id
    Broadcasts activation to blessed UI backend.
    """

@router.delete("/activate")
async def deactivate_builder_mode():
    """Deactivate builder mode (on unmount)."""
```

#### Session Management Endpoints
```python
@router.post("/session/start")
async def start_session(
    request: StartSessionRequest,
    db: Session = Depends(get_db)
) -> StartSessionResponse:
    """Start or resume builder session.

    Validates:
    - Playlist exists
    - Playlist is manual (not smart)

    Returns session metadata (no current track).
    Frontend calls /candidates/next separately.
    """

@router.get("/session/{playlist_id}")
async def get_session(
    playlist_id: int,
    db: Session = Depends(get_db)
) -> SessionResponse:
    """Get active session state."""

@router.delete("/session/{playlist_id}")
async def end_session(
    playlist_id: int,
    db: Session = Depends(get_db)
):
    """End builder session and cleanup."""
```

#### Track Operation Endpoints
```python
@router.post("/add/{playlist_id}/{track_id}")
async def add_track_to_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db)
) -> TrackActionResponse:
    """Add track to playlist.

    Returns success status. Frontend calls /candidates/next for next track.
    """

@router.post("/skip/{playlist_id}/{track_id}")
async def skip_track(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db)
) -> TrackActionResponse:
    """Skip track permanently.

    Adds track to skipped list. Frontend calls /candidates/next for next track.
    """

@router.get("/candidates/{playlist_id}/next")
async def get_next_candidate(
    playlist_id: int,
    exclude_track_id: int | None = None,
    db: Session = Depends(get_db)
) -> dict | None:
    """Get next random candidate track.

    Excludes last processed track for variety.
    Returns None if no candidates available.

    Query params:
        exclude_track_id: Track ID to exclude (typically last processed)
    """
```

#### Filter Management Endpoints
```python
@router.get("/filters/{playlist_id}")
async def get_filters(
    playlist_id: int,
    db: Session = Depends(get_db)
) -> FiltersResponse:
    """Get current builder filters."""

@router.put("/filters/{playlist_id}")
async def update_filters(
    playlist_id: int,
    request: UpdateFiltersRequest,
    db: Session = Depends(get_db)
):
    """Update builder filters (atomic replace).

    Validates filters using domain logic.
    """

@router.delete("/filters/{playlist_id}")
async def clear_filters(
    playlist_id: int,
    db: Session = Depends(get_db)
):
    """Remove all builder filters."""
```

#### Review Endpoints
```python
@router.get("/candidates/{playlist_id}")
async def get_candidates(
    playlist_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
) -> CandidatesResponse:
    """Get paginated list of candidate tracks."""

@router.get("/skipped/{playlist_id}")
async def get_skipped_tracks(
    playlist_id: int,
    db: Session = Depends(get_db)
) -> SkippedTracksResponse:
    """Get list of skipped tracks for review."""

@router.delete("/skipped/{playlist_id}/{track_id}")
async def unskip_track(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db)
):
    """Remove track from skipped list."""
```

### 2. Add Pydantic Schemas (`web/backend/schemas.py`)

```python
class StartSessionRequest(BaseModel):
    playlist_id: int

class StartSessionResponse(BaseModel):
    session_id: int
    playlist_id: int
    started_at: str
    updated_at: str
    # Note: No current_track - frontend calls /candidates/next separately

class TrackActionResponse(BaseModel):
    success: bool
    # Note: No next_track - frontend calls /candidates/next separately

class Filter(BaseModel):
    field: str
    operator: str
    value: str
    conjunction: str = "AND"

class UpdateFiltersRequest(BaseModel):
    filters: list[Filter]

class FiltersResponse(BaseModel):
    filters: list[Filter]

class CandidatesResponse(BaseModel):
    candidates: list[dict]
    total: int
    limit: int
    offset: int

class SkippedTracksResponse(BaseModel):
    skipped: list[dict]
    total: int
```

### 3. Register Router (`web/backend/main.py`)

Add to router registration section:
```python
from .routers import builder

app.include_router(builder.router, prefix="/api/builder", tags=["builder"])
```

### Error Handling

All endpoints should handle:
- **400 Bad Request**: Invalid filters, smart playlist selected
- **404 Not Found**: Playlist doesn't exist
- **500 Internal Server Error**: Database errors

Example:
```python
from fastapi import HTTPException

# Validate playlist type
playlist = get_playlist_by_id(playlist_id)
if not playlist:
    raise HTTPException(status_code=404, detail="Playlist not found")
if playlist['type'] != 'manual':
    raise HTTPException(status_code=400, detail="Only manual playlists supported")
```

## Acceptance Criteria

1. All endpoints implemented with proper HTTP methods
2. Pydantic schemas validate request/response data
3. Manual playlist validation enforced
4. Proper error responses (400, 404, 500)
5. Router registered in main.py
6. Endpoints call domain logic functions (no business logic in routes)
7. Database connection uses dependency injection

## Dependencies
- Task 01: Database migration
- Task 02: Domain logic (builder.py)

## Testing

Create tests in `web/backend/tests/test_builder_routes.py`:
```python
def test_start_session_manual_playlist():
    """Test starting session for manual playlist."""

def test_start_session_rejects_smart_playlist():
    """Test smart playlists are rejected."""

def test_add_track_advances_to_next():
    """Test add operation returns next candidate."""

def test_skip_track_adds_to_skipped_list():
    """Test skip operation updates database."""

def test_filters_update_affects_candidates():
    """Test filter changes affect candidate pool."""
```

Run with: `uv run pytest web/backend/tests/test_builder_routes.py`
