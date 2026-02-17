---
task: 04-backend-api-refactor
status: pending
depends: [03-database-layer-refactor]
files:
  - path: web/backend/routers/comparisons.py
    action: modify
  - path: web/backend/sync_manager.py
    action: modify
  - path: web/backend/schemas.py
    action: modify
---

# Backend API Refactoring

## Context
Remove session creation/caching, mode branching, and prefetch logic from backend. Simplify to single playlist-based mode with stateless queries. Remove sync manager caching and consolidate request/response schemas.

## Files to Modify/Create
- web/backend/routers/comparisons.py (modify - remove ~180 lines, add ~60 lines)
- web/backend/sync_manager.py (modify - remove ~50 lines, add ~10 lines)
- web/backend/schemas.py (modify - remove ~30 lines, add ~15 lines)

## Implementation Details

### 1. Simplify Comparison Endpoints (comparisons.py)

**Replace `POST /comparisons/session` with `POST /comparisons/start`:**

```python
@router.post("/comparisons/start")
async def start_comparison(
    request: ComparisonRequest,  # Simplified schema
    db=Depends(get_db)
) -> ComparisonResponse:
    """Start comparison mode for a playlist (stateless).

    No session creation, no caching - just queries next uncompared pair.
    Returns current pair + progress.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Query for next pair (stateless, no cache check)
        try:
            track_a, track_b = get_next_playlist_pair(request.playlist_id)
            pair = ComparisonPair(track_a=track_a, track_b=track_b)
        except RankingComplete:
            # Not an error - return response with null pair to indicate completion
            pair = None
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Get progress
        progress = get_playlist_comparison_progress(request.playlist_id)

        return ComparisonResponse(
            pair=pair,
            progress=progress,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to start comparison for playlist {request.playlist_id}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Update `POST /comparisons/record`:**

```python
@router.post("/comparisons/record")
async def record_comparison(
    request: RecordComparisonRequest,
    db=Depends(get_db)
) -> ComparisonResponse:
    """Record a comparison result (no session_id needed).

    Always playlist-based. After recording, gets next pair.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get current ratings
        track_a_rating = get_playlist_elo_rating(request.track_a_id, request.playlist_id)
        track_b_rating = get_playlist_elo_rating(request.track_b_id, request.playlist_id)

        # Calculate new ratings
        k_factor = 32
        if request.winner_id == request.track_a_id:
            track_a_new, track_b_new = calculate_elo_update(
                track_a_rating, track_b_rating, k_factor, winner="a"
            )
        else:
            track_b_new, track_a_new = calculate_elo_update(
                track_b_rating, track_a_rating, k_factor, winner="b"
            )

        # Record comparison (no session_id, single transaction)
        record_playlist_comparison(
            playlist_id=request.playlist_id,
            track_a_id=request.track_a_id,
            track_b_id=request.track_b_id,
            winner_id=request.winner_id,
            track_a_rating_before=track_a_rating,
            track_b_rating_before=track_b_rating,
            track_a_rating_after=track_a_new,
            track_b_rating_after=track_b_new,
            session_id="",  # Empty string for sessionless
        )

        # Get next pair (stateless)
        try:
            track_a, track_b = get_next_playlist_pair(request.playlist_id)
            next_pair = ComparisonPair(track_a=track_a, track_b=track_b)
        except RankingComplete:
            next_pair = None  # Ranking complete

        progress = get_playlist_comparison_progress(request.playlist_id)

        return ComparisonResponse(
            pair=next_pair,
            progress=progress,
        )

    except Exception as e:
        logger.exception("Failed to record comparison")
        raise HTTPException(status_code=500, detail=str(e))
```

**Delete from comparisons.py:**
- All session creation/resume logic (lines 205-227)
- All mode-specific branching (global vs playlist)
- All sync_manager caching calls

### 2. Remove Sync Manager Caching (sync_manager.py)

**Remove methods:**
- `get_playlist_pair()`
- `set_playlist_pair()`
- `clear_playlist_pair()`
- `active_playlist_pairs` dict

**Keep only WebSocket broadcasts:**

```python
class SyncManager:
    def __init__(self):
        self.connected_clients: list = []

    def broadcast_comparison_update(self, playlist_id: int, data: dict) -> None:
        """Broadcast comparison update to all connected devices.

        No caching - just notifies devices that a comparison happened.
        Devices re-query for next pair themselves.
        """
        message = {
            "type": "comparison_update",
            "playlist_id": playlist_id,
            "progress": data.get("progress"),
            # No pair data - devices query themselves
        }
        for client in self.connected_clients:
            # WebSocket send implementation
            pass
```

### 3. Consolidate Schemas (schemas.py)

**Remove session_id and ranking_mode:**

```python
class ComparisonPair(BaseModel):
    track_a: TrackInfo
    track_b: TrackInfo

class ComparisonRequest(BaseModel):  # Unified request schema
    playlist_id: int  # REQUIRED - no optional modes

class RecordComparisonRequest(BaseModel):
    playlist_id: int
    track_a_id: int
    track_b_id: int
    winner_id: int

class ComparisonProgress(BaseModel):
    compared: int
    total: int
    percentage: float

class ComparisonResponse(BaseModel):  # Unified response schema
    pair: Optional[ComparisonPair]  # None when ranking complete
    progress: ComparisonProgress
```

**Delete old schemas:**
- `StartSessionRequest`
- `StartSessionResponse`
- Any schemas with `session_id` or `ranking_mode` fields

## Verification

Test API endpoints:
```bash
# Test start endpoint
curl -X POST http://localhost:8642/api/comparisons/start \
  -H "Content-Type: application/json" \
  -d '{"playlist_id": 1}'

# Should return: {pair: {...}, progress: {...}}
# No session_id, no prefetched_pair

# Test record endpoint
curl -X POST http://localhost:8642/api/comparisons/record \
  -H "Content-Type: application/json" \
  -d '{
    "playlist_id": 1,
    "track_a_id": 123,
    "track_b_id": 456,
    "winner_id": 123
  }'

# Should return: {pair: {...}, progress: {...}}
# No session_id in request or response
```

Test ranking completion:
```bash
# Create small test playlist with 3 tracks
# Rank all pairs (3 comparisons total)
# Verify: Next /start call returns completion message
```
