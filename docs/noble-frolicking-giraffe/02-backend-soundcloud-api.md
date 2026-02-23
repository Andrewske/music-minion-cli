---
task: 02-backend-soundcloud-api
status: done
depends:
  - 01-backend-track-search
files:
  - path: web/backend/routers/soundcloud.py
    action: modify
  - path: web/backend/schemas.py
    action: modify
  - path: src/music_minion/domain/library/providers/soundcloud/api.py
    action: reference
  - path: src/music_minion/domain/library/deduplication.py
    action: reference
  - path: src/music_minion/domain/playlists/crud.py
    action: reference
---

# Backend: SoundCloud Import API Endpoints

## Context
Three endpoints to support the import wizard: list user's playlists, match a playlist's tracks to local library, and create a local playlist from matches.

## Files to Modify/Create
- `web/backend/routers/soundcloud.py` (modify)
- `web/backend/schemas.py` (modify - add Pydantic models)
- `web/backend/soundcloud_auth.py` (create - ProviderState helper)

## Implementation Details

### ProviderState Helper (soundcloud_auth.py)

```python
"""SoundCloud auth helper for web backend."""
import json
from pathlib import Path
from music_minion.domain.library.provider import ProviderState

def get_web_provider_state() -> ProviderState | None:
    """Load SoundCloud ProviderState from saved tokens.

    Returns None if not authenticated.
    """
    token_path = Path.home() / ".music-minion" / "soundcloud_token.json"
    if not token_path.exists():
        return None
    try:
        token_data = json.loads(token_path.read_text())
        return ProviderState(authenticated=True, cache={"token_data": token_data})
    except (json.JSONDecodeError, KeyError):
        return None
```

### Pydantic Models (schemas.py)

```python
class ScPlaylistMatch(BaseModel):
    sc_track_id: str
    sc_title: str
    sc_artist: str
    local_track_id: int | None = None
    local_title: str | None = None
    local_artist: str | None = None
    confidence: float
    is_approved: bool = False
    is_missing: bool = False
    sc_position: int | None = None

class MatchPlaylistResponse(BaseModel):
    playlist_name: str
    sc_playlist_id: str
    matches: list[ScPlaylistMatch]
    auto_approved_count: int
    needs_review_count: int

class CreatePlaylistRequest(BaseModel):
    playlist_name: str
    sc_playlist_id: str
    matches: list[ScPlaylistMatch]

class CreatePlaylistResponse(BaseModel):
    playlist_id: int
    track_count: int
```

### Endpoint 1: List Playlists

```python
@router.get("/playlists")
async def get_soundcloud_playlists():
    """Get user's SoundCloud playlists.

    Returns: [{id, name, track_count}]
    """
```

Uses existing `get_playlists()` from `providers/soundcloud/api.py`.

### Endpoint 2: Match Playlist (Synchronous)

```python
@router.post("/match-playlist")
async def match_playlist(playlist_id: str) -> MatchPlaylistResponse:
    """Match SoundCloud playlist tracks to local library.

    - Fetches tracks from SoundCloud
    - Runs TF-IDF matching against local library
    - Auto-approves matches ≥0.85 confidence
    - Returns all matches sorted by confidence (low to high)
    """
```

**Logic:**
1. Get ProviderState via `get_web_provider_state()` (return 401 if None)
2. Call `get_playlist_tracks(state, playlist_id)`
3. Get local tracks from database: `SELECT * FROM tracks WHERE local_path IS NOT NULL`
4. Call `find_best_matches_tfidf(sc_tracks, local_tracks, min_score=0.0)`
5. For each match:
   - Set `is_approved = True` if confidence ≥ 0.85
   - Set `sc_position` from original playlist order (enumerate index)
   - Extract `local_track_id = match["id"]` from returned dict
6. Sort matches by confidence ascending (low first for review)
7. Return with counts

**Error Handling:**
- No auth token: Return 401 with message "SoundCloud not authenticated"
- Empty local library: Return matches with all `local_track_id = None`
- Invalid playlist ID: Return 404
- Network timeout: Return 503 with retry message

### Endpoint 3: Create Playlist from Matches

```python
@router.post("/create-playlist-from-matches")
async def create_playlist_from_matches(request: CreatePlaylistRequest) -> CreatePlaylistResponse:
    """Create local playlist from matched tracks.

    - Creates playlist with given name
    - Adds matched tracks (excluding is_missing) in sc_position order
    - Links playlist to SoundCloud playlist ID for future sync
    - Sets soundcloud_id on matched local tracks for sync support
    """
```

**Logic:**
1. Filter matches: exclude `is_missing = True`, keep only `local_track_id IS NOT NULL`
2. Sort remaining matches by `sc_position` ascending (preserve playlist order)
3. Create playlist via `create_playlist(name, "manual")`
4. Link to SC: `UPDATE playlists SET soundcloud_playlist_id = ? WHERE id = ?`
5. Add tracks via `add_tracks_to_playlist(playlist_id, [m.local_track_id for m in sorted_matches])`
6. **Set soundcloud_id on matched tracks:**
   ```python
   for match in sorted_matches:
       conn.execute(
           "UPDATE tracks SET soundcloud_id = ? WHERE id = ?",
           (match.sc_track_id, match.local_track_id)
       )
   ```
7. Return playlist_id and track_count

**Error Handling:**
- Duplicate playlist name: Return 409 with message "Playlist name already exists"
- No valid matches: Return 400 with message "No tracks to add"

## Verification

```bash
# List playlists
curl http://localhost:8642/api/soundcloud/playlists

# Match a playlist (replace ID)
curl -X POST http://localhost:8642/api/soundcloud/match-playlist \
  -H "Content-Type: application/json" \
  -d '{"playlist_id": "123456789"}'

# Create playlist from matches
curl -X POST http://localhost:8642/api/soundcloud/create-playlist-from-matches \
  -H "Content-Type: application/json" \
  -d '{"playlist_name": "My Import", "sc_playlist_id": "123", "matches": [...]}'
```
