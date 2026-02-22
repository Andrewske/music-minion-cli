---
task: 03-bucket-backend-api
status: complete
depends: [01-database-migration, 02-emoji-source-type-updates]
files:
  - path: web/backend/routers/buckets.py
    action: create
  - path: web/backend/queries/buckets.py
    action: create
  - path: web/backend/main.py
    action: modify
---

# Backend API for Bucket Sessions

## Context
Create the FastAPI router and query functions for managing bucket sessions, buckets, and track assignments with emoji integration.

## Files to Modify/Create
- web/backend/routers/buckets.py (new)
- web/backend/queries/buckets.py (new)
- web/backend/main.py (modify - register router)

## Implementation Details

### 1. Create `web/backend/queries/buckets.py`

Database query functions:

```python
import uuid
from datetime import datetime
from music_minion.core.database import get_db_connection
from web.backend.queries.emojis import add_emoji_to_track_mutation, remove_emoji_from_track_mutation

def get_or_create_session(playlist_id: int) -> dict:
    """
    Get active session for playlist or create new one.
    Idempotent: partial unique index guarantees single active session per playlist.
    On resume: reconciles bucket_tracks against current playlist_tracks
      - Removes orphaned tracks (no longer in playlist)
      - New playlist tracks appear in unassigned_track_ids
    """

def get_session_with_data(session_id: str) -> dict:
    """Get session with all buckets and track assignments."""

def create_bucket(session_id: str, name: str, emoji_id: str | None, position: int) -> dict:
    """Create a new bucket in the session."""

def update_bucket(bucket_id: str, name: str | None, emoji_id: str | None) -> dict:
    """
    Update bucket name/emoji.
    Emoji change propagation:
      1. If old emoji exists: remove from all bucket tracks (by source_id=bucket_id)
      2. If new emoji set: add to all bucket tracks with source_type='bucket', source_id=bucket_id
      3. Batch operations with executemany() for efficiency
    """

def delete_bucket(bucket_id: str) -> bool:
    """Delete bucket, remove its emojis from all tracks, return tracks to unassigned."""

def move_bucket(bucket_id: str, direction: str) -> bool:
    """Swap bucket position with neighbor."""

def shuffle_bucket_tracks(bucket_id: str) -> list[int]:
    """Randomize track order within bucket, return new order."""

def assign_track_to_bucket(bucket_id: str, track_id: int) -> dict:
    """
    Assign track to bucket:
    1. If track in another bucket, remove it (and its emoji)
    2. Add to new bucket at end
    3. If bucket has emoji, add it to track with source_id=bucket_id
    """

def unassign_track(bucket_id: str, track_id: int) -> bool:
    """Remove track from bucket, remove bucket's emoji from track."""

def reorder_bucket_tracks(bucket_id: str, track_ids: list[int]) -> bool:
    """Update position values for tracks in bucket."""

def apply_session(session_id: str) -> bool:
    """
    Apply bucket order to playlist:
    1. Get all tracks from buckets in order (bucket position, then track position within bucket)
    2. Get unassigned tracks in their original relative order
    3. Update playlist_tracks positions: bucket tracks first, then unassigned appended at end
    4. Mark session as 'applied'

    Unassigned tracks are NOT removed - they are appended after all bucket tracks.
    """

def discard_session(session_id: str) -> bool:
    """
    Discard session:
    1. Remove all bucket emojis from tracks
    2. Mark session as 'discarded'
    """
```

### 2. Create `web/backend/routers/buckets.py`

FastAPI router:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/buckets", tags=["buckets"])

# Session endpoints
@router.post("/sessions")
async def create_or_resume_session(body: CreateSessionBody) -> SessionResponse:
    """Create or resume session for playlist."""

@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> SessionResponse:
    """Get session with buckets and track assignments."""

@router.delete("/sessions/{session_id}")
async def discard_session(session_id: str) -> dict:
    """Discard session (removes bucket emojis from tracks)."""

@router.post("/sessions/{session_id}/apply")
async def apply_session(session_id: str) -> dict:
    """Apply order to playlist."""

# Bucket endpoints
@router.post("/sessions/{session_id}/buckets")
async def create_bucket(session_id: str, body: CreateBucketBody) -> BucketResponse:
    """Create bucket."""

@router.patch("/{bucket_id}")
async def update_bucket(bucket_id: str, body: UpdateBucketBody) -> BucketResponse:
    """Update bucket (name, emoji)."""

@router.delete("/{bucket_id}")
async def delete_bucket(bucket_id: str) -> dict:
    """Delete bucket."""

@router.post("/{bucket_id}/move")
async def move_bucket(bucket_id: str, body: MoveBucketBody) -> dict:
    """Move bucket up/down."""

@router.post("/{bucket_id}/shuffle")
async def shuffle_bucket(bucket_id: str) -> ShuffleResponse:
    """Randomize track order within bucket."""

# Track assignment
@router.post("/{bucket_id}/tracks/{track_id}")
async def assign_track(bucket_id: str, track_id: int) -> AssignResponse:
    """Assign track to bucket."""

@router.delete("/{bucket_id}/tracks/{track_id}")
async def unassign_track(bucket_id: str, track_id: int) -> dict:
    """Unassign track from bucket."""

@router.post("/{bucket_id}/tracks/reorder")
async def reorder_tracks(bucket_id: str, body: ReorderBody) -> dict:
    """Reorder tracks within bucket."""
```

### 3. Register router in main.py

```python
from web.backend.routers import buckets
app.include_router(buckets.router)
```

### Response Types

```python
class SessionResponse(BaseModel):
    id: str
    playlist_id: int
    status: str
    buckets: list[BucketResponse]
    unassigned_track_ids: list[int]

class BucketResponse(BaseModel):
    id: str
    name: str
    emoji_id: str | None
    position: int
    track_ids: list[int]
```

## Verification
```bash
# Start the web server
uv run music-minion --web

# Create/resume session
curl -X POST http://localhost:8642/api/buckets/sessions \
  -H "Content-Type: application/json" \
  -d '{"playlist_id": 1}'

# Create bucket
curl -X POST http://localhost:8642/api/buckets/sessions/{session_id}/buckets \
  -H "Content-Type: application/json" \
  -d '{"name": "Peak Energy", "emoji_id": "🔥"}'

# Assign track
curl -X POST http://localhost:8642/api/buckets/{bucket_id}/tracks/123

# Verify emoji was added with source
sqlite3 ~/.local/share/music-minion/music_minion.db \
  "SELECT * FROM track_emojis WHERE track_id = 123 AND source_type = 'bucket'"

# Apply session
curl -X POST http://localhost:8642/api/buckets/sessions/{session_id}/apply
```
