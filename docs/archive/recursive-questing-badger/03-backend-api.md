---
task: 03-backend-api
status: done
depends: [02-crud-functions]
files:
  - path: web/backend/routers/playlists.py
    action: modify
---

# Backend API Endpoints

## Context
Expose pin/unpin/reorder functionality via REST API endpoints. These endpoints will be called by the frontend to persist pin state.

## Files to Modify/Create
- web/backend/routers/playlists.py (modify)

## Implementation Details

**Step 1: Add pin endpoint**

```python
@router.post("/playlists/{playlist_id}/pin")
async def pin_playlist_endpoint(playlist_id: int):
    """Pin a playlist to the top of the sidebar."""
    from music_minion.domain.playlists import crud
    success = crud.pin_playlist(playlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found")
    playlist = crud.get_playlist_by_id(playlist_id)
    return {"playlist": playlist}
```

**Step 2: Add unpin endpoint**

```python
@router.delete("/playlists/{playlist_id}/pin")
async def unpin_playlist_endpoint(playlist_id: int):
    """Unpin a playlist."""
    from music_minion.domain.playlists import crud
    success = crud.unpin_playlist(playlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found or not pinned")
    playlist = crud.get_playlist_by_id(playlist_id)
    return {"playlist": playlist}
```

**Step 3: Add reorder endpoint**

```python
from pydantic import BaseModel

class ReorderPinRequest(BaseModel):
    position: int

@router.patch("/playlists/{playlist_id}/pin")
async def reorder_pinned_playlist_endpoint(playlist_id: int, request: ReorderPinRequest):
    """Reorder a pinned playlist to a new position."""
    from music_minion.domain.playlists import crud
    success = crud.reorder_pinned_playlist(playlist_id, request.position)
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found or not pinned")
    playlist = crud.get_playlist_by_id(playlist_id)
    return {"playlist": playlist}
```

**Step 4: Commit**

```bash
git add web/backend/routers/playlists.py
git commit -m "feat: add pin/unpin/reorder API endpoints"
```

## Verification

Start the backend and test via curl:
```bash
# Start app in background
uv run music-minion --web &

# Test pin endpoint (replace 1 with actual playlist ID)
curl -X POST http://localhost:8642/api/playlists/1/pin

# Test unpin endpoint
curl -X DELETE http://localhost:8642/api/playlists/1/pin

# Kill background app
pkill -f "music-minion"
```
Expected: JSON response with `{"playlist": {..., "pin_order": 1}}` for pin, `null` for unpin
