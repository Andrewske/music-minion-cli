---
task: 02-genres-api-router
status: pending
depends: [01-database-migration]
files:
  - path: web/backend/routers/genres.py
    action: create
  - path: web/backend/main.py
    action: modify
---

# Backend Genres API Router

## Context
RESTful API endpoints for genre management. Handles CRUD operations, track-genre associations, and emoji propagation to tracks.

## Files to Modify/Create
- `web/backend/routers/genres.py` (new)
- `web/backend/main.py` (modify)

## Implementation Details

### New Router: `genres.py`

Follow pattern from `emojis.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["genres"])

# --- Models ---

class GenreInfo(BaseModel):
    id: int
    name: str
    emoji_id: Optional[str]
    track_count: int

class TrackGenre(BaseModel):
    id: int
    name: str
    emoji_id: Optional[str]
    position: int

class RenameGenreRequest(BaseModel):
    name: str

class AssignEmojiRequest(BaseModel):
    emoji_id: Optional[str]  # null to remove

class UpdateTrackGenresRequest(BaseModel):
    genre_ids: list[int]  # ordered by priority (first = primary)

# --- Endpoints ---

@router.get("/genres")
def list_genres() -> list[GenreInfo]:
    """List all genres with track counts, sorted by count desc."""
    # Use get_all_genres() from database.py

@router.put("/genres/{genre_id}")
def rename_genre(genre_id: int, request: RenameGenreRequest) -> GenreInfo:
    """Rename genre. If name exists, merge genres."""
    # Use rename_genre() from database.py
    # Return updated genre info

@router.put("/genres/{genre_id}/emoji")
def assign_genre_emoji(genre_id: int, request: AssignEmojiRequest) -> GenreInfo:
    """Assign emoji to genre. Propagates to track_emojis for all tracks."""
    # 1. Update genres.emoji_id
    # 2. For all tracks with this genre:
    #    - Remove old track_emojis where source_type='genre' and source_id=genre_name
    #    - If emoji_id not null: Add track_emojis with source_type='genre', source_id=genre_name

@router.delete("/genres/{genre_id}")
def delete_genre(genre_id: int) -> dict:
    """Delete genre from all tracks."""
    # 1. Remove all track_genres entries
    # 2. Remove track_emojis where source_type='genre' and source_id=genre_name
    # 3. Delete genre record
    return {"deleted": True}

@router.get("/tracks/{track_id}/genres")
def get_track_genres(track_id: int) -> list[TrackGenre]:
    """Get ordered genres for a track."""
    # Use get_track_genres() from database.py

@router.put("/tracks/{track_id}/genres")
def update_track_genres(track_id: int, request: UpdateTrackGenresRequest) -> list[TrackGenre]:
    """Update track's genres (ordered by position). Writes primary to file."""
    # 1. Call set_track_genres() - handles DB + tracks.genre field
    # 2. Update file metadata if local track
    # 3. Handle emoji propagation:
    #    - Remove old genre-sourced emojis
    #    - Add emojis for new genres that have emoji_id set
```

### Emoji Propagation Logic

When a genre is assigned an emoji:
1. Query all tracks with that genre from `track_genres`
2. Remove existing `track_emojis` entries where `source_type='genre'` AND `source_id=<old_genre_name>`
3. Insert new `track_emojis` entries with `source_type='genre'`, `source_id=<genre_name>`

When a track's genres change:
1. Get old genres for track
2. Get new genres for track
3. For removed genres: delete `track_emojis` where `source_type='genre'` AND `source_id=<removed_genre_name>`
4. For added genres with emoji_id: insert `track_emojis`

### Register Router

In `main.py`:
```python
from .routers import genres
app.include_router(genres.router, prefix="/api")
```

## Verification

```bash
# Start the app
cd ~/coding/music-minion-cli
uv run music-minion --web

# Test endpoints (in another terminal)
curl http://localhost:8642/api/genres | jq

# Test rename
curl -X PUT http://localhost:8642/api/genres/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "New Genre Name"}' | jq

# Test emoji assignment
curl -X PUT http://localhost:8642/api/genres/1/emoji \
  -H "Content-Type: application/json" \
  -d '{"emoji_id": "fire"}' | jq
```
